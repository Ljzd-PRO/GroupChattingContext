import csv
import os
import time
from collections import deque

from pkg.core.entities import LauncherTypes, Query
from pkg.plugin.context import APIHost, BasePlugin, EventContext, handler, register
from pkg.plugin.events import (  # 导入事件类
    GroupMessageReceived,
    NormalMessageResponded,
    PromptPreProcessing,
)
from pkg.provider import entities as llm_entities


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

    # 异步初始化
    async def initialize(self):
        self.ap.logger.info("🧩 [GroupChattingContext] 插件初始化")

    # 收到群聊消息时，写入历史记录
    # TODO rule filter，只记录开启聊天的群
    @handler(GroupMessageReceived)
    async def group_message_received(self, ctx: EventContext):
        if ctx.event.query is None:
            return
        if ctx.event.query.launcher_type != LauncherTypes.GROUP:
            return

        self._write_history(
            session_name=f"{ctx.event.query.launcher_type.value}_{ctx.event.query.launcher_id}",
            query=ctx.event.query,
        )

    # 发送 prompt 时，读取历史记录
    @handler(PromptPreProcessing)
    async def prompt_pre_processing(self, ctx: EventContext):
        """追加会话历史"""
        if ctx.event.query is None:
            return
        if ctx.event.query.launcher_type != LauncherTypes.GROUP:
            return

        history = self._make_history_propmt(self._read_history(ctx.event.session_name))  # type: ignore

        # 修改当前消息
        # 参考 preproc.py 中的 events.PromptPreProcessing
        if history and history != "":
            ctx.event.query.message_chain.insert(0, f"{history}\n\n")
            ctx.event.query.message_chain.insert(
                1, f"{ctx.event.query.sender_id} 对你说："
            )

    # 收到大模型回复消息时，读取历史记录注入持久化 conversation, 清空历史记录
    @handler(NormalMessageResponded)
    async def normal_message_responded(self, ctx: EventContext):
        if ctx.event.query is None:
            return
        if ctx.event.query.launcher_type != LauncherTypes.GROUP:
            return
        session_name = (
            f"{ctx.event.query.launcher_type.value}_{ctx.event.query.launcher_id}"
        )

        # 注入聊天历史记录
        session = await self.ap.sess_mgr.get_session(ctx.event.query)
        conversation = await self.ap.sess_mgr.get_conversation(session)
        rows = self._read_history(session_name)
        history = self._make_history_propmt(rows)
        last_row = rows[-1] if rows else None
        if last_row:
            # 本轮对话者的持久化信息，因为 message 还没写进去，所以 append 在上一轮
            history += f"\n\n然后 {ctx.event.query.sender_id} 对你说："
        if history and history != "":
            # 新建fake历史
            conversation.messages.append(
                llm_entities.Message(role="user", content=history)
            )
            conversation.messages.append(
                llm_entities.Message(role="assistant", content="(观察上下文中)")
            )

        self.ap.logger.info(
            f"\n[%%注入之后的 message] message: {conversation.messages}\n"
        )

        self._clear_history(
            session_name=f"{ctx.event.query.launcher_type.value}_{ctx.event.query.launcher_id}"
        )

    def _make_history_propmt(self, rows: list[list[str]] | None) -> str:
        if rows is None:
            return ""

        history_lines = []
        for row in rows[-20:-1]:
            if len(row) >= 3:
                senderid = row[0].strip()
                content = row[2].strip()
                history_lines.append(f"{senderid} 说：{content}")

        # 按时间顺序排列（从旧到新）
        return "\n".join(history_lines)

    def _read_history(self, session_name: str) -> list[list[str]] | None:
        """从文件读取历史记录

        输出为 list<str> f"{senderid}说:{content}"
        """
        file_path = os.path.join(self.data_dir, f"{session_name}.csv")
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                rows = list(reader)

                if not rows:
                    return None

                # 检查并跳过表头
                start_index = 0
                if rows[0] == ["senderid", "timestamp", "content"]:
                    start_index = 1

                # 只保留最多20条记录（与写入逻辑保持一致）
                # 但是最后一条消息是重复的，需要截断
                return rows[start_index:]

        except Exception as e:
            self.ap.logger.info(f"读取历史记录失败: {str(e)}\n")
            return None

    # 存储历史记录到文件
    def _write_history(self, session_name: str, query: Query) -> None:
        sender_id = query.sender_id
        content = str(query.message_chain)
        timestamp = int(time.time())
        file_path = os.path.join(self.data_dir, f"{session_name}.csv")

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # 新数据行
        new_row = [str(sender_id), str(timestamp), content]

        # 读取现有数据
        rows = []
        header = ["senderid", "timestamp", "content"]

        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                try:
                    rows = list(reader)
                except csv.Error:
                    rows = []

        # 分离表头和数据
        data = deque(maxlen=20)
        if rows:
            # 验证表头
            if rows[0] == header:
                data.extend(rows[1:])
            else:
                # 处理没有表头的情况
                data.extend(rows)

        # 添加新数据
        data.append(new_row)
        self.ap.logger.info(
            f"[GroupChattingContext] {session_name} 写入新消息: {new_row}\n"
        )

        # 写入文件
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow(header)
            writer.writerows(data)

        return

    # 清除历史记录
    def _clear_history(self, session_name: str) -> None:
        file_path = os.path.join(self.data_dir, f"{session_name}.csv")
        if os.path.exists(file_path):
            # 读取文件并清空内容
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                f.write("")
