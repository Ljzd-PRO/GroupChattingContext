import csv
import os
import time
from collections import deque

from pkg.core import app
from pkg.core.entities import Query


class HistoryMgr:
    def __init__(self, ap: app.Application):
        self.ap = ap

        self.data_dir = os.path.join(".", "data", "plugins", "GroupChattingContext")
        self.csv_header = ["sender_id", "timestamp", "content"]

    def read(self, session_name: str) -> list[list[str]] | None:
        """从文件读取历史记录
        输出为 list of ["sender_id", "timestamp", "content"]
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
                if rows[0] == self.csv_header:
                    start_index = 1

                # 只保留最多20条记录（与写入逻辑保持一致）
                # 但是最后一条消息是重复的，需要截断
                return rows[start_index:]

        except Exception as e:
            self.ap.logger.info(f"读取历史记录失败: {str(e)}\n")
            return None

    def write(self, session_name: str, query: Query) -> None:
        """写入指定 session 历史记录"""
        sender_id = query.sender_id
        content = str(query.message_chain)
        timestamp = int(time.time())
        file_path = os.path.join(self.data_dir, f"{session_name}.csv")

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # 新数据行
        new_row = [str(sender_id), str(timestamp), content]

        # 读取现有数据
        rows = []

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
            if rows[0] == self.csv_header:
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
            writer.writerow(self.csv_header)
            writer.writerows(data)

        return

    def clear(self, session_name: str) -> None:
        """清除指定 session 历史记录"""
        file_path = os.path.join(self.data_dir, f"{session_name}.csv")
        if os.path.exists(file_path):
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                # 写入空内容
                f.write("")
