"""
engines/primitives/registry.py — Global primitive registry.
"""

from typing import Optional
from engines.primitives.base import BasePrimitive

_primitives: dict[str, BasePrimitive] = {}


def register(primitive: BasePrimitive) -> None:
    _primitives[primitive.primitive_id] = primitive


def get_primitive(primitive_id: str) -> Optional[BasePrimitive]:
    return _primitives.get(primitive_id)


def list_primitives() -> list[dict]:
    return [
        {
            "type": p.primitive_id,
            "name": p.name,
            "description": p.description,
            "config_schema": p.get_config_schema(),
            "actions": p.actions,
        }
        for p in _primitives.values()
    ]
