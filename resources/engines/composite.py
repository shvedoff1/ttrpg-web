"""
engines/composite.py — CompositeEngine: runs user-defined mechanics.

A user engine stores a list of mechanics in UserEngine.mechanics:
  [
    {
      "type":   "weighted_roll",   # must match a registered primitive_id
      "label":  "Травы",           # display name for this mechanic
      "action": "roll",            # default action to call (optional)
      "config": {...}              # mechanic-specific config
    },
    ...
  ]

When an action is dispatched to CompositeEngine:
  - action format: "<mechanic_index>:<primitive_action>" (e.g. "0:roll", "2:list_contexts")
  - for single-mechanic engines, plain action without index is accepted
"""

from fastapi import HTTPException
from engines.base import BaseEngine
from engines.primitives.registry import get_primitive, list_primitives


class CompositeEngine(BaseEngine):
    engine_id = "composite"
    name = "Пользовательский движок"
    description = "Движок, собранный из примитивных механик"

    def get_meta(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "name": self.name,
            "description": self.description,
            "actions": [],
            "primitives": list_primitives(),
        }

    def get_default_config(self) -> dict:
        return {"mechanics": []}

    def handle_action(self, action: str, payload: dict, config: dict) -> dict:
        mechanics: list[dict] = config.get("mechanics") or []
        if not mechanics:
            raise HTTPException(400, "This engine has no mechanics configured")

        # Parse "index:action" format (e.g. "0:roll", "2:list_contexts")
        if ":" in action:
            idx_str, prim_action = action.split(":", 1)
            try:
                idx = int(idx_str)
            except (ValueError, TypeError):
                raise HTTPException(400, f"Invalid mechanic index: '{idx_str}'")
        elif len(mechanics) == 1:
            idx = 0
            prim_action = action or mechanics[0].get("action") or "roll"
        else:
            raise HTTPException(
                400,
                f"Multi-mechanic engine requires 'index:action' format, got: '{action}'",
            )

        if idx < 0 or idx >= len(mechanics):
            raise HTTPException(400, f"Mechanic index {idx} out of range (0..{len(mechanics) - 1})")

        mechanic = mechanics[idx]
        primitive = get_primitive(mechanic["type"])
        if not primitive:
            raise HTTPException(400, f"Unknown mechanic type: {mechanic['type']}")

        return primitive.execute(prim_action, payload, mechanic.get("config") or {})
