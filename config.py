import json
import os
from dataclasses import dataclass


@dataclass
class RuleObject:
    limit: int
    propmt: str
    self_name: str | None
    """历史记录中自身的称呼（回复语句），为空则使用Bot的ID"""


class Config:
    def __init__(self) -> None:
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, mode="r", encoding="utf-8") as f:
            self.data = json.load(f)
            pass

    def get_by_group_id(self, group_id: str | int) -> RuleObject:
        if group_id and str(group_id) in self.data:
            return RuleObject(
                limit=self.data[str(group_id)]["limit"],
                propmt=self.data[str(group_id)]["propmt"],
                self_name=self.data[str(group_id)].get("self_name"),
            )
        else:
            return RuleObject(
                limit=self.data["default"]["limit"],
                propmt=self.data["default"]["propmt"],
                self_name=self.data["default"].get("self_name"),
            )

    def get_by_session_name(self, session_name: str) -> RuleObject:
        return self.get_by_group_id(session_name.split("_")[-1])
