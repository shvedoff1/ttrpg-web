"""
engines/story_motivation.py — Random story motivations for characters.

Actions:
  get_motivations → roll N motivations (payload: {count?})

Delegates to WeightedSamplePrimitive.
"""

from fastapi import HTTPException
from engines.base import BaseEngine
from engines.primitives.weighted_sample import WeightedSamplePrimitive

_MOTIVATIONS_FILE = "config.motivation.default"

_sample = WeightedSamplePrimitive()


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
            count = min(int(payload.get("count", 3)), 20)
            return _sample.execute("sample", {"count": count}, {
                "data_source": config.get("motivations_file", _MOTIVATIONS_FILE),
                "items_key": "motivations",
                "default_count": 3,
            })
        raise HTTPException(400, f"Unknown action: {action}")
