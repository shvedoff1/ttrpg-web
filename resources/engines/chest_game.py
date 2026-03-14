"""
engines/chest_game.py — Chest mini-game (sequence guessing).

Actions:
  start  → start new chest game (payload: {chest})
  guess  → guess a direction (payload: {game_id, direction})
  list   → list available chests
"""

import random
import uuid
from fastapi import HTTPException
from engines.base import BaseEngine
from engines._helpers import load_json

_CHESTS_CONFIG = "config.chest_game.default"
_DIR_ICON = {"up": "↑", "down": "↓", "left": "←", "right": "→"}

# In-memory active games (shared across all instances)
_active_games: dict[str, dict] = {}


def _roll_chest(config: dict, chest_key: str) -> dict:
    chest_cfg = config.get(chest_key)
    if not chest_cfg:
        raise HTTPException(422, f"Unknown chest: {chest_key}")

    gold = random.randint(chest_cfg["gold_min"], chest_cfg["gold_max"])
    item_count = random.randint(chest_cfg["items_min"], chest_cfg["items_max"])

    pool: dict = {}
    for cat_file in chest_cfg.get("categories", []):
        pool.update(load_json(cat_file))

    entries = [(k, d) for k, d in pool.items() if (d.get("probability") or 0) > 0]
    display_name = chest_cfg.get("name", chest_key)

    if not entries:
        return {"name": display_name, "gold": gold, "items": []}

    total = sum(d["probability"] for _, d in entries)
    items: list[str] = []
    for _ in range(item_count):
        r = random.random() * total
        for _, d in entries:
            r -= d["probability"]
            if r <= 0:
                items.append(d["name"])
                break
        else:
            items.append(entries[-1][1]["name"])

    return {"name": display_name, "gold": gold, "items": items}


class ChestGameEngine(BaseEngine):
    engine_id = "chest_game"
    name = "Мини-игра: сундуки"
    description = "Угадай последовательность направлений чтобы открыть сундук"

    def get_meta(self) -> dict:
        return {
            "engine_id": self.engine_id,
            "name": self.name,
            "description": self.description,
            "actions": [
                {
                    "id": "list",
                    "label": "Список сундуков",
                    "params": [],
                },
                {
                    "id": "start",
                    "label": "Открыть сундук",
                    "params": [{"name": "chest", "type": "string", "required": True}],
                },
                {
                    "id": "guess",
                    "label": "Угадать направление",
                    "params": [
                        {"name": "game_id", "type": "string", "required": True},
                        {"name": "direction", "type": "string", "required": True},
                    ],
                },
            ],
        }

    def get_default_config(self) -> dict:
        return {"config_file": _CHESTS_CONFIG}

    def get_config_schema(self) -> dict:
        return {"fields": [
            {"key": "config_file", "type": "slug_picker", "label": "Конфиг сундуков",
             "slug_type": "engine_config", "engine_filter": "chest_game"},
        ]}

    def handle_action(self, action: str, payload: dict, config: dict) -> dict:
        cfg_file = config.get("config_file", _CHESTS_CONFIG)

        if action == "list":
            cfg = load_json(cfg_file)
            return {
                "chests": [
                    {"key": k, "name": v.get("name", k)}
                    for k, v in cfg.items()
                ]
            }

        if action == "start":
            chest_key = payload.get("chest")
            if not chest_key:
                raise HTTPException(422, "chest required")
            cfg = load_json(cfg_file)
            chest_cfg = cfg.get(chest_key)
            if not chest_cfg:
                raise HTTPException(422, f"Unknown chest: {chest_key}")

            game_cfg = chest_cfg.get("game", {})
            length = game_cfg.get("length", 3)
            directions = game_cfg.get("directions", ["up", "down", "left", "right"])
            sequence = [random.choice(directions) for _ in range(length)]

            game_id = str(uuid.uuid4())
            _active_games[game_id] = {
                "sequence": sequence,
                "current_index": 0,
                "attempts": 0,
                "chest_key": chest_key,
                "config_file": cfg_file,
            }
            return {
                "game_id": game_id,
                "length": length,
                "directions": directions,
                "combination": [_DIR_ICON.get(d, d) for d in sequence],
            }

        if action == "guess":
            game_id = payload.get("game_id")
            direction = payload.get("direction")
            if not game_id or not direction:
                raise HTTPException(422, "game_id and direction required")

            game = _active_games.get(game_id)
            if not game:
                raise HTTPException(422, f"Game not found: {game_id}")

            correct = game["sequence"][game["current_index"]] == direction

            if correct:
                game["current_index"] += 1
                guessed = game["sequence"][: game["current_index"]]
                done = game["current_index"] == len(game["sequence"])

                if done:
                    cfg = load_json(game["config_file"])
                    result = _roll_chest(cfg, game["chest_key"])
                    del _active_games[game_id]
                    return {
                        "correct": True,
                        "done": True,
                        "guessed": [_DIR_ICON.get(d, d) for d in guessed],
                        "attempts": game["attempts"],
                        "result": result,
                    }
                return {
                    "correct": True,
                    "done": False,
                    "guessed": [_DIR_ICON.get(d, d) for d in guessed],
                    "attempts": game["attempts"],
                }
            else:
                game["attempts"] += 1
                guessed = game["sequence"][: game["current_index"]]
                return {
                    "correct": False,
                    "done": False,
                    "guessed": [_DIR_ICON.get(d, d) for d in guessed],
                    "attempts": game["attempts"],
                }

        raise HTTPException(400, f"Unknown action: {action}")
