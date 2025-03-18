import asyncio
from collections import defaultdict

from pkg.core.entities import LauncherTypes
from pkg.plugin.context import APIHost, BasePlugin, EventContext, handler, register
from pkg.plugin.events import (  # 导入事件类
    GroupMessageReceived,
    NormalMessageResponded,
    PromptPreProcessing,
)
from pkg.provider import entities as llm_entities
from plugins.GroupChattingContext.history import HistoryMgr


# 注册插件
@register(
    name="GroupChattingContext",  # 英文名
    description="群聊回复时发送完整的历史记录",  # 中文描述
    version="0.1.0",
    author="Sansui233",
)
class GroupChattingContext(BasePlugin):
    def __init__(self, host: APIHost):
        self.data_dir = "./data/plugins/GroupChattingContext"
        self.history_mgr = HistoryMgr(self.ap)
        self.history_edit_locks = defaultdict(asyncio.Lock)

    # 异步初始化
    async def initialize(self):
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

    # 发送 prompt 时，读取历史记录，并修改发送的消息
    @handler(PromptPreProcessing)
    async def prompt_pre_processing(self, ctx: EventContext):
        if (
            ctx.event.query is None
            or ctx.event.query.launcher_type != LauncherTypes.GROUP
            or not self._validate_group(ctx.event.query.launcher_id)
        ):
            return

        history = self._make_history_propmt(self._read_history(ctx.event.session_name))  # type: ignore

        # 修改当前消息
        # 参考 preproc.py 中的 events.PromptPreProcessing
        if history and history != "":
            ctx.event.query.message_chain.insert(0, f"{history}\n\n")
            ctx.event.query.message_chain.insert(
                1, f"现在，{ctx.event.query.sender_id} 说："
            )

    # 收到大模型回复消息时，历史记录注入持久化 conversation, 清空历史记录
    @handler(NormalMessageResponded)
    async def normal_message_responded(self, ctx: EventContext):
        if (
            ctx.event.query is None
            or ctx.event.query.launcher_type != LauncherTypes.GROUP
            or not self._validate_group(ctx.event.query.launcher_id)
        ):
            return

        session_name = (
            f"{ctx.event.query.launcher_type.value}_{ctx.event.query.launcher_id}"
        )

        # 注入聊天历史记录
        lock = self.history_edit_locks[session_name]
        async with lock:
            session = await self.ap.sess_mgr.get_session(ctx.event.query)
            conversation = await self.ap.sess_mgr.get_conversation(session)
            rows = self.history_mgr.read(session_name)
            history = self._make_history_propmt(rows)
            last_row = rows[-1] if rows else None
            if last_row:
                # 本轮对话者的持久化信息，因为 无法控制本轮对话的 message, 所以 append 在上一轮
                history += f"\n\n然后 {ctx.event.query.sender_id} 说："
            if history and history != "":
                # 新建fake历史
                conversation.messages.append(
                    llm_entities.Message(role="user", content=history)
                )
                conversation.messages.append(
                    llm_entities.Message(role="assistant", content="（观察对话中）")
                )

            # self.ap.logger.info(
            #     f"\n[%%注入之后的 message] message: {conversation.messages}\n"
            # )

            self.history_mgr.clear(
                session_name=f"{ctx.event.query.launcher_type.value}_{ctx.event.query.launcher_id}"
            )

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

        for row in rows[-20:end]:
            if len(row) >= 3:
                sender_id = row[0].strip()
                content = row[2].strip()
                history_lines.append(f"{sender_id} 说：{content}")

        # 按时间顺序排列（从旧到新）
        return "\n".join(history_lines)
