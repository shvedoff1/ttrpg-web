"""
engines/story_motivation.py — Random story motivations for characters.

Actions:
  get_motivations → roll N motivations (payload: {count?})
"""

import random
from fastapi import HTTPException
from engines.base import BaseEngine
from engines._helpers import load_json

_MOTIVATIONS_FILE = "config.motivation.default"


def _roll_motivations(data: dict, count: int = 3) -> list[str]:
    entries = [
        (m["name"], m.get("weight", 1))
        for m in data["motivations"]
        if (m.get("weight") or 0) > 0
    ]
    result: list[str] = []
    available = list(entries)
    for _ in range(min(count, len(available))):
        total = sum(w for _, w in available)
        r = random.random() * total
        chosen_idx = len(available) - 1
        for i, (_, w) in enumerate(available):
            r -= w
            if r <= 0:
                chosen_idx = i
                break
        result.append(available[chosen_idx][0])
        available.pop(chosen_idx)
    return result


class StoryMotivationEngine(BaseEngine):
    engine_id = "story_motivation"
    name = "Мотивации персонажей"
    description = "Случайные мотивации для NPC и игровых персонажей"

    def get_meta(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "name": self.name,
            "description": self.description,
            "actions": [
                {
                    "id": "get_motivations",
                    "label": "Получить мотивации",
                    "params": [
                        {"name": "count", "type": "integer", "required": False,
                         "default": 3},
                    ],
                },
            ],
        }

    def get_default_config(self) -> dict:
        return {"motivations_file": _MOTIVATIONS_FILE}

    def get_config_schema(self) -> dict:
        return {"fields": [
            {"key": "motivations_file", "type": "slug_picker", "label": "Конфиг мотиваций",
             "slug_type": "engine_config", "engine_filter": "story_motivation"},
        ]}

    def handle_action(self, action: str, payload: dict, config: dict) -> dict:
        if action == "get_motivations":
            cfg_file = config.get("motivations_file", _MOTIVATIONS_FILE)
            count = min(int(payload.get("count", 3)), 20)
            data = load_json(cfg_file)
            return {"motivations": _roll_motivations(data, count)}

        raise HTTPException(400, f"Unknown action: {action}")
