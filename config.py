import json
import os
from dataclasses import dataclass


@dataclass
class RuleObject:
    limit: int
    propmt: str


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
            )
        else:
            return RuleObject(
                limit=self.data["default"]["limit"],
                propmt=self.data["default"]["propmt"],
            )

    def get_by_session_name(self, session_name: str) -> RuleObject:
        return self.get_by_group_id(session_name.split("_")[-1])
