import asyncio
import copy
from collections import defaultdict
from typing import cast

from pkg.core.entities import LauncherTypes, Query
from pkg.plugin.context import APIHost, BasePlugin, EventContext, handler, register
from pkg.plugin.events import (  # 导入事件类
    GroupMessageReceived,
    NormalMessageResponded,
    PromptPreProcessing,
)
from pkg.provider import entities as llm_entities
from plugins.GroupChattingContext.config import Config
from plugins.GroupChattingContext.history import HistoryMgr


# 注册插件
@register(
    name="GroupChattingContext",  # 英文名
    description="群聊回复时发送群聊历史记录、每个群聊单独追加 prompt",  # 中文描述
    version="0.1.0",
    author="Sansui233",
)
class GroupChattingContext(BasePlugin):
    def __init__(self, host: APIHost):
        self.conf = Config()
        self.history_mgr = HistoryMgr(self.conf)
        self.history_edit_locks = defaultdict(asyncio.Lock)

    # 异步初始化
    async def initialize(self):
        await self.history_mgr.initialize(self.ap)
        self.ap.logger.info("🧩 [GroupChattingContext] 插件初始化")

    # 收到群聊消息时，写入历史记录
    @handler(GroupMessageReceived)
    async def group_message_received(self, ctx: EventContext):
        if (
            ctx.event.query is None
            or ctx.event.query.launcher_type != LauncherTypes.GROUP
            or not self._validate_group(ctx.event.query.launcher_id)
        ):
            return

        session_name = (
            f"{ctx.event.query.launcher_type.value}_{ctx.event.query.launcher_id}"
        )

        lock = self.history_edit_locks[session_name]
        async with lock:
            self.history_mgr.write(session_name, query=ctx.event.query)

    # 发送 prompt 时，读取历史记录，并修改发送的消息。并持久化历史记录至会话，最后删除历史记录
    @handler(PromptPreProcessing)
    async def prompt_pre_processing(self, ctx: EventContext):
        if (
            ctx.event.query is None
            or ctx.event.query.launcher_type != LauncherTypes.GROUP
            or not self._validate_group(ctx.event.query.launcher_id)
        ):
            return

        session_name = ctx.event.session_name  # type: ignore
        history = self._make_history_propmt(
            self.history_mgr.read(session_name)  # type: ignore
        )

        #  default_prompt(=query.prompt.messages=系统人格) 和 prompt（=query.messages=会话消息=历史记录） 和 当前用户消息
        #  req_messages = query.prompt.messages.copy() + query.messages.copy() + [query.user_message]

        # 修改当前发给 AI 的 user_message( 由message_chain 构建)，注入发送者 id
        cast(llm_entities.Message, ctx.event.query.user_message)
        if ctx.event.query.user_message:
            if type(ctx.event.query.user_message.content) is str:
                ctx.event.query.user_message.content = f"{history}\n\n 现在，{ctx.event.query.sender_id} 说：{ctx.event.query.user_message.content}"
            elif type(ctx.event.query.user_message.content) is list:
                ctx.event.query.user_message.content.insert(
                    0,
                    llm_entities.ContentElement.from_text(f"{history}\n"),
                )
                ctx.event.query.user_message.content.insert(
                    1,
                    llm_entities.ContentElement.from_text(
                        f"{history}\n\n 现在，{ctx.event.query.sender_id} 说："
                    ),
                )

        ctx.event = cast(PromptPreProcessing, ctx.event)
        ctx.event.query = cast(Query, ctx.event.query)

        # 修改发送的 default_prompt
        processed_prompt = copy.deepcopy(ctx.event.default_prompt)
        group_prompt = self.conf.get_by_group_id(ctx.event.query.launcher_id).propmt
        if len(processed_prompt) > 0:
            if type(processed_prompt[0].content) is str:
                processed_prompt[0].content += "\n\n" + group_prompt
            elif type(processed_prompt[0].content) is list:
                processed_prompt[0].content.append(
                    llm_entities.ContentElement.from_text("\n" + group_prompt)
                )
        ctx.add_return("default_prompt", processed_prompt)

        self.history_mgr.clear(session_name)

    def _validate_group(self, group_id: int | str) -> bool:
        rules = self.ap.pipeline_cfg.data["respond-rules"]
        if str(group_id) in rules:
            rule = rules[str(group_id)]
            if "at" in rule and (rule["at"]):
                return True

        return False

    def _make_history_propmt(self, rows: list[list[str]] | None, strip=True) -> str:
        """构建历史记录prompt
        {sender_id} 说：{content}\n

        strip = True 会忽略历史记录文件中的最后一行。
        history 文件中的最后一行是触发回复的句子，
        是会自动记录的所以需要去掉
        """
        if rows is None:
            return ""

        history_lines = []
        end = -1 if strip else 0

        for row in rows[:end]:
            if len(row) >= 3:
                sender_id = row[0].strip()
                content = row[2].strip()
                history_lines.append(f"{sender_id} 说：{content}")

        # 按时间顺序排列（从旧到新）
        return "\n".join(history_lines)
