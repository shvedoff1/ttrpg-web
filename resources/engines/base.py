"""
engines/base.py — BaseEngine abstract class.

Every engine must:
  - Define class-level: engine_id, name, description
  - Implement get_meta() → dict  with available actions
  - Implement handle_action(action, payload, config) → dict
"""

from abc import ABC, abstractmethod
from typing import ClassVar


class BaseEngine(ABC):
    engine_id: ClassVar[str] = ""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    @abstractmethod
    def get_meta(self) -> dict:
        """
        Return engine metadata for UI and API discovery.

        Expected shape:
        {
            "engine_id": "...",
            "name": "...",
            "description": "...",
            "actions": [
                {"id": "roll", "label": "Сделать ролл", "params": [...]}
            ]
        }
        """

    def get_default_config(self) -> dict:
        """Return the default config keys this engine uses when game config is empty."""
        return {}

    def get_config_schema(self) -> dict:
        """Return structured config field descriptions for visual editors."""
        return {"fields": []}

    @abstractmethod
    def handle_action(self, action: str, payload: dict, config: dict) -> dict:
        """
        Execute an engine action.

        Args:
            action:  action identifier (must match one from get_meta()["actions"])
            payload: request-specific parameters
            config:  game-specific engine config (from game_engines.config),
                     may be empty — engines fall back to defaults

        Returns:
            dict with the action result

        Raises:
            fastapi.HTTPException on invalid input / not found
        """
