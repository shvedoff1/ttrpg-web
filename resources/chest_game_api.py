"""
Chest game API — mini-game for opening chests (sequence guessing).

Two endpoints:
- POST /api/play/chest-start: start a game, get game_id and length
- POST /api/play/chest-guess: guess a direction, get feedback and result
"""

from fastapi import APIRouter, HTTPException, Response
from pathlib import Path
import json
import random
import string
import uuid

router = APIRouter()

# In-memory storage of active games
chest_games: dict = {}  # game_id → { sequence, current_index, attempts, chest_key }

RESOURCES_DIR = Path(__file__).parent / "jsons"
CHESTS_CONFIG_FILE = "configs/chests_config.json"


def safe_path(filename: str) -> Path:
    if not filename.endswith(".json") or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = (RESOURCES_DIR / filename).resolve()
    if not path.is_relative_to(RESOURCES_DIR.resolve()):
        raise HTTPException(400, "Invalid filename")
    return RESOURCES_DIR / filename


def _load_json(filename: str) -> dict | list:
    path = safe_path(filename)
    if not path.exists():
        raise HTTPException(404, f"Data file not found: {filename}")
    return json.loads(path.read_text(encoding="utf-8"))


def _roll_cache(config: dict, chest_key: str) -> dict:
    """Roll cache/chest contents: gold + items."""
    chest_cfg = config.get(chest_key)
    if not chest_cfg:
        raise HTTPException(422, f"Unknown chest: {chest_key}")

    gold = random.randint(chest_cfg["gold_min"], chest_cfg["gold_max"])
    item_count = random.randint(chest_cfg["items_min"], chest_cfg["items_max"])

    pool: dict = {}
    for cat_file in chest_cfg.get("categories", []):
        pool.update(_load_json(cat_file))

    entries = [(key, data) for key, data in pool.items() if (data.get("probability") or 0) > 0]
    display_name = chest_cfg.get("name", chest_key)

    if not entries:
        return {"name": display_name, "gold": gold, "items": []}

    total = sum(data["probability"] for _, data in entries)
    items: list[str] = []
    for _ in range(item_count):
        r = random.random() * total
        for _, data in entries:
            r -= data["probability"]
            if r <= 0:
                items.append(data["name"])
                break
        else:
            items.append(entries[-1][1]["name"])

    return {"name": display_name, "gold": gold, "items": items}


DIR_ICON_MAP = {"up": "↑", "down": "↓", "left": "←", "right": "→"}


@router.post("/api/play/chest-start")
async def chest_start(body: dict, response: Response):
    """
    Start a chest game.
    Body: { "chest": "common" }
    Returns: { "game_id": "...", "length": N }
    """
    chest_key = body.get("chest")
    if not chest_key:
        raise HTTPException(422, "chest key required")

    config = _load_json(CHESTS_CONFIG_FILE)
    chest_cfg = config.get(chest_key)
    if not chest_cfg:
        raise HTTPException(422, f"Unknown chest: {chest_key}")

    game_cfg = chest_cfg.get("game", {})
    length = game_cfg.get("length", 3)
    directions = game_cfg.get("directions", ["up", "down", "left", "right"])

    # Generate random sequence
    sequence = [random.choice(directions) for _ in range(length)]

    # Store game
    game_id = str(uuid.uuid4())
    chest_games[game_id] = {
        "sequence": sequence,
        "current_index": 0,
        "attempts": 0,
        "chest_key": chest_key,
    }

    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return {"game_id": game_id, "length": length, "directions": directions}


@router.post("/api/play/chest-guess")
async def chest_guess(body: dict, response: Response):
    """
    Guess a direction in the chest game.
    Body: { "game_id": "...", "direction": "up" }
    Returns: { "correct": bool, "done": bool, "guessed": [...], "attempts": N, [result: {...}] }
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"

    game_id = body.get("game_id")
    direction = body.get("direction")

    if not game_id or not direction:
        raise HTTPException(422, "game_id and direction required")

    game = chest_games.get(game_id)
    if not game:
        raise HTTPException(422, f"Game not found: {game_id}")

    correct = game["sequence"][game["current_index"]] == direction

    if correct:
        game["current_index"] += 1
        guessed = game["sequence"][: game["current_index"]]
        done = game["current_index"] == len(game["sequence"])

        if done:
            # Game complete: roll the chest and clean up
            config = _load_json(CHESTS_CONFIG_FILE)
            result = _roll_cache(config, game["chest_key"])
            del chest_games[game_id]
            return {
                "correct": True,
                "done": True,
                "guessed": [DIR_ICON_MAP.get(d, d) for d in guessed],
                "attempts": game["attempts"],
                "result": result,
            }
        else:
            return {
                "correct": True,
                "done": False,
                "guessed": [DIR_ICON_MAP.get(d, d) for d in guessed],
                "attempts": game["attempts"],
            }
    else:
        # Wrong guess
        game["attempts"] += 1
        guessed = game["sequence"][: game["current_index"]]
        return {
            "correct": False,
            "done": False,
            "guessed": [DIR_ICON_MAP.get(d, d) for d in guessed],
            "attempts": game["attempts"],
        }
