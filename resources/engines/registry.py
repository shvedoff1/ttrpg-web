"""
engines/registry.py — Global engine registry.

Usage:
    from engines.registry import register, get_engine, list_engines

    register(MyEngine())          # in web_app.py startup
    engine = get_engine("my_id")  # in router
    all_meta = list_engines()     # GET /api/engines
"""

from typing import Optional
from engines.base import BaseEngine

_registry: dict[str, BaseEngine] = {}


def register(engine: BaseEngine) -> None:
    _registry[engine.engine_id] = engine


def get_engine(engine_id: str) -> Optional[BaseEngine]:
    return _registry.get(engine_id)


def list_engines() -> list[dict]:
    return [e.get_meta() for e in _registry.values()]
