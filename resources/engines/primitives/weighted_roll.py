"""
primitives/weighted_roll.py — Pick one item from a weighted list.
"""

from engines.primitives.base import BasePrimitive
from engines._helpers import load_json, roll_weighted, get_effective_items


class WeightedRollPrimitive(BasePrimitive):
    primitive_id = "weighted_roll"
    name = "Взвешенный бросок"
    description = "Случайный выбор одного предмета из списка с вероятностями"

    def get_config_schema(self) -> dict:
        return {"fields": [
            {"key": "show_price", "type": "boolean", "label": "Показывать цену"},
        ]}

    def get_binding_schema(self) -> dict:
        return {"roles": [
            {"id": "source", "label": "Набор ресурсов", "multiple": False},
        ]}

    def execute(self, action: str, payload: dict, config: dict) -> dict:
        bindings = config.get("_bindings")
        if bindings:
            return self._execute_bindings(action, payload, config, bindings)
        return self._execute_legacy(action, payload, config)

    def _execute_bindings(self, action, payload, config, bindings):
        source = [b for b in bindings if b.role == "source"]
        if not source:
            return {"name": "Ничего не нашли"}
        items = get_effective_items(source[0])
        resources = {it["name"]: it["probability"] for it in items if (it.get("probability") or 0) > 0}
        result = roll_weighted(resources)
        item_data = next((it for it in items if it["name"] == result["name"]), {})
        result["price"] = item_data.get("price")
        result["weight"] = item_data.get("weight")
        return result

    def _execute_legacy(self, action, payload, config):
        if not config.get("data_source"):
            return {"error": True, "html": "Этот движок требует настройки через Категорию. Добавьте привязки ресурсов в настройках категории."}
        data = load_json(config["data_source"])
        resources = {
            k: v.get("probability", 0)
            for k, v in data.items()
            if isinstance(v, dict) and (v.get("probability") or 0) > 0
        }
        result = roll_weighted(resources)
        item = data.get(result["name"], {}) if isinstance(data.get(result["name"]), dict) else {}
        result["price"] = item.get("price")
        result["weight"] = item.get("weight")
        return result
