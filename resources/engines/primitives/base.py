"""
engines/primitives/base.py — BasePrimitive abstract class.

Every primitive must:
  - Define class-level: primitive_id, name, description
  - Implement execute(action, payload, config) → dict
"""

from abc import ABC, abstractmethod
from typing import ClassVar


class BasePrimitive(ABC):
    primitive_id: ClassVar[str] = ""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    actions: ClassVar[list[dict]] = [{"id": "roll", "label": "Бросок"}]

    def get_meta(self) -> dict:
        """Return metadata for frontend rendering."""
        return {
            "engine_id": self.primitive_id,
            "name": self.name,
            "description": self.description,
            "actions": list(self.actions),
        }

    def get_config_schema(self) -> dict:
        """Return config field descriptions for visual editors."""
        return {"fields": []}

    def get_binding_schema(self) -> dict:
        """Return expected resource binding roles for this primitive."""
        return {"roles": [{"id": "source", "label": "Источник данных", "multiple": False}]}

    @abstractmethod
    def execute(self, action: str, payload: dict, config: dict) -> dict:
        """Execute a primitive action and return the result.

        config may contain '_bindings' (list of EngineResourceBinding)
        for the new resource binding system, or legacy slug-based fields.
        """
