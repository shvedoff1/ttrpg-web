import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import json
import random
import subprocess
import sys
import hashlib
from pathlib import Path
from typing import Optional
import markdown
from routers.auth import router as auth_router
from routers.games import router as games_router
from routers.engines import router as engines_router
from routers.user_engines import router as user_engines_router
from routers.libraries import router as libraries_router
from routers.log import router as log_router
from routers.categories import router as categories_router
from routers.resources import router as resources_router
from routers.bindings import router as bindings_router
from core.database import SessionLocal
from core.models import DataLibrary
from item_generator import generate_items
from engines import registry as engine_registry
from engines.profession_roll import ProfessionRollEngine
from engines.chest_game import ChestGameEngine
from engines.item_gen import ItemGenEngine
from engines.trader_inventory import TraderInventoryEngine
from engines.story_motivation import StoryMotivationEngine
from engines.treasure import TreasureEngine
from engines.composite import CompositeEngine
from engines.primitives import register_all_primitives

RESOURCES_DIR = Path(__file__).parent / "jsons"
STATIC_DIR = Path(__file__).parent / "static"
CHANGELOG_FILE = Path(__file__).parent / "static" / "changelog.html"

# Register primitives first, then engines
register_all_primitives()
engine_registry.register(ProfessionRollEngine())
engine_registry.register(ChestGameEngine())
engine_registry.register(ItemGenEngine())
engine_registry.register(TraderInventoryEngine())
engine_registry.register(StoryMotivationEngine())
engine_registry.register(TreasureEngine())
engine_registry.register(CompositeEngine())


def _make_db_resolver() -> dict:
    """Загружает все системные библиотеки в память. Возвращает slug→data кеш."""
    db = SessionLocal()
    try:
        rows = db.query(DataLibrary).filter(DataLibrary.owner_id.is_(None)).all()
        return {row.slug: row.data for row in rows}
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from core.seed import run_seed
    from core.seed_libraries import run_seed_libraries
    from core.seed_resources import run_seed_resources
    from engines._helpers import set_db_resolver

    run_seed()
    run_seed_libraries()
    run_seed_resources()

    # Кешируем системные библиотеки in-memory для быстрого доступа из движков
    _sys_cache = _make_db_resolver()

    def _resolve_slug(slug: str) -> dict | list:
        # Сначала ищем в кеше системных библиотек
        if slug in _sys_cache:
            return _sys_cache[slug]
        # Пользовательские библиотеки — из БД
        db = SessionLocal()
        try:
            row = db.query(DataLibrary).filter(DataLibrary.slug == slug).first()
            if not row:
                from fastapi import HTTPException
                raise HTTPException(404, f"Library not found: {slug}")
            return row.data
        finally:
            db.close()

    set_db_resolver(_resolve_slug)
    yield


app = FastAPI(title="Gothic Resources", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(games_router)
app.include_router(engines_router)
app.include_router(user_engines_router)
app.include_router(libraries_router)
app.include_router(log_router)
app.include_router(categories_router)
app.include_router(resources_router)
app.include_router(bindings_router)



def safe_path(filename: str) -> Path:
    if not filename.endswith(".json") or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = (RESOURCES_DIR / filename).resolve()
    if not path.is_relative_to(RESOURCES_DIR.resolve()):
        raise HTTPException(400, "Invalid filename")
    return RESOURCES_DIR / filename


# ── Play configuration ────────────────────────────────────────────────────────

PROFESSION_SOURCES: dict[str, tuple[str, str]] = {
    "Травы":  ("items.alchemy.herbs",            "config.profession_roll.herbs"),
    "Руды":   ("items.craft.ores",               "config.profession_roll.ores"),
    "Следы":  ("items.hunt.trophies",            "config.profession_roll.trophies"),
}

STEAL_CONFIG_FILE       = "config.profession_roll.steal"
CACHE_CONFIG_FILE       = "config.profession_roll.cache"
CHESTS_CONFIG_FILE      = "config.chest_game.default"
TREASURE_FILE           = "config.treasure.default"
STANDARD_TRADERS_FILE   = "config.trader.standard"
STORES_FILE             = "config.trader.named"
MOTIVATIONS_FILE        = "config.motivation.default"
TRADER_COEFF_DEFAULT    = 1.5


def _load_json(filename: str) -> dict | list:
    path = safe_path(filename)
    if not path.exists():
        raise HTTPException(404, f"Data file not found: {filename}")
    return json.loads(path.read_text(encoding="utf-8"))


# ── Roll helpers ──────────────────────────────────────────────────────────────

def _roll_weighted(resources: dict) -> dict:
    entries = [(name, w) for name, w in resources.items() if (w or 0) > 0]
    if not entries:
        return {"name": "Ничего не нашли"}
    total = sum(w for _, w in entries)
    r = random.random() * total
    for name, w in entries:
        r -= w
        if r <= 0:
            return {"name": name}
    return {"name": entries[-1][0]}


def _roll_with_locations(items: dict, location: dict) -> dict:
    overrides = location.get("overrides", {})
    entries = []
    for key, w in overrides.items():
        if (w or 0) <= 0:
            continue
        item = items.get(key)
        if item:
            entries.append({"name": item["name"], "price": item.get("price"), "w": w})
    if not entries:
        return {"name": "Ничего не нашли"}
    total = sum(e["w"] for e in entries)
    r = random.random() * total
    for e in entries:
        r -= e["w"]
        if r <= 0:
            return {"name": e["name"], "price": e["price"]}
    last = entries[-1]
    return {"name": last["name"], "price": last["price"]}


def _roll_treasure(data: dict) -> dict:
    cat_entries = [(k, v) for k, v in data["categories"].items() if (v.get("weight") or 0) > 0]
    if not cat_entries:
        raise HTTPException(500, "treasure.json has no valid categories")
    cat_total = sum(v["weight"] for _, v in cat_entries)
    r = random.random() * cat_total
    chosen_cat_key, chosen_cat = cat_entries[-1]
    for key, v in cat_entries:
        r -= v["weight"]
        if r <= 0:
            chosen_cat_key, chosen_cat = key, v
            break

    items = _load_json(chosen_cat["resource_file"])
    entries = [it for it in items.values() if (it.get("probability") or 0) > 0]
    if not entries:
        raise HTTPException(500, f"No items in {chosen_cat['resource_file']}")
    item_total = sum(it["probability"] for it in entries)
    r2 = random.random() * item_total
    chosen = entries[-1]
    for it in entries:
        r2 -= it["probability"]
        if r2 <= 0:
            chosen = it
            break
    return {"name": chosen["name"], "price": chosen.get("price"), "category": chosen_cat["label"]}


def _roll_steal(config: dict, district: str) -> dict:
    pool: dict = {}
    for cat_file in config.get("categories", []):
        pool.update(_load_json(cat_file))

    entries = sorted(
        [(key, data) for key, data in pool.items() if (data.get("probability") or 0) > 0],
        key=lambda x: x[1]["probability"],
    )
    n = len(entries)
    if n == 0:
        return {"name": "Ничего не нашли"}

    filter_cfg = config.get("district_filter", {}).get(district, {})
    ftype   = filter_cfg.get("filter", "")
    cut     = int(n * filter_cfg.get("percent", 0) / 100)

    if ftype == "exclude_rarest" and cut > 0:
        entries = entries[cut:]
    elif ftype == "exclude_common" and cut > 0:
        entries = entries[:-cut]

    if not entries:
        return {"name": "Ничего не нашли"}

    total = sum(data["probability"] for _, data in entries)
    r = random.random() * total
    for _, data in entries:
        r -= data["probability"]
        if r <= 0:
            return {"name": data["name"]}
    return {"name": entries[-1][1]["name"]}


def _roll_cache(config: dict, district: str) -> dict:
    district_cfg = config.get(district)
    if not district_cfg:
        raise HTTPException(422, f"Unknown cache district: {district}")

    gold = random.randint(district_cfg["gold_min"], district_cfg["gold_max"])
    item_count = random.randint(district_cfg["items_min"], district_cfg["items_max"])

    pool: dict = {}
    for cat_file in district_cfg.get("categories", []):
        pool.update(_load_json(cat_file))

    entries = [(key, data) for key, data in pool.items() if (data.get("probability") or 0) > 0]
    display_name = district_cfg.get("name", district)

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


def _roll_merged_items(pool: dict, coefficient: float) -> dict:
    entries = [it for it in pool.values() if (it.get("probability") or 0) > 0]
    if not entries:
        return {"name": "Ничего нет"}
    total = sum(it["probability"] for it in entries)
    r = random.random() * total
    for it in entries:
        r -= it["probability"]
        if r <= 0:
            price = it.get("price")
            return {"name": it["name"], "price": round(price * coefficient) if price else None}
    last = entries[-1]
    price = last.get("price")
    return {"name": last["name"], "price": round(price * coefficient) if price else None}


def _sample_weighted(entries: list, count: int) -> list:
    """Взвешенная выборка без повторов из списка предметов."""
    available = list(entries)
    result = []
    for _ in range(min(count, len(available))):
        total = sum(it.get("probability", 0) for it in available)
        if total <= 0:
            break
        r = random.random() * total
        chosen_idx = len(available) - 1
        for i, it in enumerate(available):
            r -= it.get("probability", 0)
            if r <= 0:
                chosen_idx = i
                break
        result.append(available[chosen_idx])
        available.pop(chosen_idx)
    return result


def _build_trader_inventory(categories: list, objects_count: Optional[int]) -> dict:
    """Формирует пул инвентаря торговца по приоритетам.

    Если objects_count None — вычисляет как sum(count) из всех категорий.
    Затем выбирает товары по приоритетам (убывание).
    """
    # Если objects_count не задан, вычисляем как сумму всех count
    if objects_count is None:
        objects_count = sum(cat.get("count", 0) for cat in categories)

    # Группируем по приоритету
    groups = {}
    for cat in categories:
        p = cat["priority"]
        groups.setdefault(p, []).append(cat)

    result = {}
    slots = objects_count

    # Проходим по приоритетам (от высшего к низшему)
    for priority in sorted(groups.keys(), reverse=True):
        if slots <= 0:
            break
        group = groups[priority]
        pool = {}
        for cat in group:
            if "generate" in cat:
                # Генерируем предметы вместо загрузки из файла
                generated = generate_items(
                    cat["generate"],
                    cat.get("subtype", ""),
                    cat["count"]
                )
                for it in generated:
                    pool[it["name"]] = it
            else:
                # Стандартная загрузка из файла
                pool.update(_load_json(cat["resource_file"]))

        sum_count = sum(c["count"] for c in group)
        take = min(slots, sum_count)

        # Взвешенный ролл take предметов без повторов
        entries = [it for it in pool.values() if (it.get("probability") or 0) > 0]
        if entries:
            taken = _sample_weighted(entries, take)
            for it in taken:
                # Используем name как ключ для дедупликации
                result[it["name"]] = it
            slots -= len(taken)

    return result





@app.post("/api/generate")
async def generate():
    try:
        proc = subprocess.run(
            [sys.executable, "generator.py"],
            cwd=str(RESOURCES_DIR),
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
        )
        output = proc.stdout + proc.stderr
        res_path = RESOURCES_DIR.parent / "res.json"
        result_data = (
            json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else None
        )
        return {
            "status": "ok" if proc.returncode == 0 else "error",
            "output": output,
            "result": result_data,
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "output": "Timeout (30s)", "result": None}
    except Exception as e:
        return {"status": "error", "output": str(e), "result": None}


@app.get("/api/result")
async def get_result():
    res_path = RESOURCES_DIR.parent / "res.json"
    if not res_path.exists():
        raise HTTPException(404, "res.json not found — сначала запустите генератор")
    return json.loads(res_path.read_text(encoding="utf-8"))


@app.get("/api/play/profession/{name}/locations")
async def play_profession_locations(name: str):
    if name not in PROFESSION_SOURCES:
        raise HTTPException(404, f"Unknown profession: {name}")
    _, loc_file = PROFESSION_SOURCES[name]
    locs = _load_json(loc_file)
    return {
        "mode": "with_locations",
        "locations": [{"key": key, "name": loc["name"]} for key, loc in locs.items()],
    }


# ── Traders cache ─────────────────────────────────────────────────────────────
TRADERS_CACHE: dict[str, dict] = {}


def _get_cache_key(subtype: str, key: str) -> str:
    return f"{subtype}:{key}"


def _reset_traders_cache():
    global TRADERS_CACHE
    TRADERS_CACHE.clear()


@app.get("/api/play/traders/named")
async def play_traders_named():
    stores = _load_json(STORES_FILE)
    return [{"key": key, "name": store["name"]} for key, store in stores.items()]


@app.get("/api/play/traders/inventory/{subtype}/{key}")
async def play_trader_inventory(subtype: str, key: str):
    cache_key = _get_cache_key(subtype, key)

    # Проверяем кеш
    if cache_key in TRADERS_CACHE:
        return TRADERS_CACHE[cache_key]

    unique_keys: set[str] = set()

    if subtype == "standard":
        traders = _load_json(STANDARD_TRADERS_FILE)
        trader = traders.get(key)
        if not trader:
            raise HTTPException(422, f"Unknown trader template: {key}")
        categories = trader.get("categories", [])
        coefficient = trader.get("coefficient", TRADER_COEFF_DEFAULT)
        pool = _build_trader_inventory(categories, trader.get("objects_count"))

    elif subtype == "named":
        stores = _load_json(STORES_FILE)
        store = stores.get(key)
        if not store:
            raise HTTPException(422, f"Unknown named store: {key}")
        categories = store.get("categories", [])
        coefficient = store.get("coefficient", TRADER_COEFF_DEFAULT)
        pool = _build_trader_inventory(categories, store.get("objects_count"))
        # Добавляем уникальные предметы
        for k, v in (store.get("resources_override") or {}).items():
            pool[k] = {"probability": 100, **v, "_unique": True}
            unique_keys.add(k)
    else:
        raise HTTPException(422, f"Unknown subtype: {subtype}")

    items_raw = [
        {
            "name":        it["name"],
            "probability": it.get("probability", 0),
            "price":       round(it["price"] * coefficient) if it.get("price") else None,
            "unique":      k in unique_keys,
            "parts":       it.get("parts"),
            "properties":  it.get("properties"),
        }
        for k, it in pool.items()
        if (it.get("probability") or 0) > 0
    ]
    items_raw.sort(key=lambda x: x["probability"], reverse=True)
    items = [
        {
            "name": i["name"],
            "price": i["price"],
            "unique": i["unique"],
            "parts": i["parts"],
            "properties": i["properties"],
        }
        for i in items_raw
    ]
    result = {"items": items, "coefficient": coefficient}

    # Кешируем результат
    TRADERS_CACHE[cache_key] = result
    return result


@app.post("/api/play/roll")
async def play_roll(request: Request):
    body = await request.json()
    roll_type = body.get("type")

    if roll_type == "profession":
        profession = body.get("profession", "")

        if profession == "Воровство":
            param1 = body.get("param1")
            param2 = body.get("param2")
            if not param1 or not param2:
                raise HTTPException(422, "param1 and param2 required for Воровство")
            if param1 == "steal":
                return _roll_steal(_load_json(STEAL_CONFIG_FILE), param2)
            elif param1 == "cache":
                return _roll_cache(_load_json(CACHE_CONFIG_FILE), param2)
            else:
                raise HTTPException(422, f"Unknown param1: {param1}")

        if profession not in PROFESSION_SOURCES:
            raise HTTPException(422, f"Unknown profession: {profession}")
        location_key = body.get("location")
        if not location_key:
            raise HTTPException(422, "location required")
        item_file, loc_file = PROFESSION_SOURCES[profession]
        items = _load_json(item_file)
        locs = _load_json(loc_file)
        location = locs.get(location_key)
        if not location:
            raise HTTPException(422, f"Unknown location: {location_key}")
        return _roll_with_locations(items, location)

    if roll_type == "chests":
        chest_key = body.get("chest")
        if not chest_key:
            raise HTTPException(422, "chest key required")
        return _roll_cache(_load_json(CHESTS_CONFIG_FILE), chest_key)

    if roll_type == "treasure":
        return _roll_treasure(_load_json(TREASURE_FILE))

    raise HTTPException(422, f"Unknown roll type: {roll_type}")


# ── Item generation endpoints ──────────────────────────────────────────────────

@app.get("/api/generate/weapon")
async def generate_weapon(subtype: str = Query("sword"), count: int = Query(1, ge=1, le=100)):
    """Generate weapons with parts and properties.

    Query params:
    - subtype: weapon type (default: "sword")
    - count: number of items to generate (1-100, default: 1)
    """
    try:
        items = generate_items("weapon", subtype, count)
        return {"items": items}
    except ValueError as e:
        raise HTTPException(422, str(e))
    except FileNotFoundError as e:
        raise HTTPException(422, str(e))


@app.get("/api/generate/armor")
async def generate_armor(subtype: str = Query("heavy"), count: int = Query(1, ge=1, le=100)):
    """Generate armor with parts and properties.

    Query params:
    - subtype: armor type (default: "heavy")
    - count: number of items to generate (1-100, default: 1)
    """
    try:
        items = generate_items("armor", subtype, count)
        return {"items": items}
    except ValueError as e:
        raise HTTPException(422, str(e))
    except FileNotFoundError as e:
        raise HTTPException(422, str(e))


# ── Story endpoints ────────────────────────────────────────────────────────────

def _roll_motivations(data: dict, count: int = 3) -> list[str]:
    entries = [(m["name"], m.get("weight", 1)) for m in data["motivations"] if (m.get("weight") or 0) > 0]
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


@app.post("/api/play/story/motivation")
async def play_story_motivation():
    data = _load_json(MOTIVATIONS_FILE)
    return {"motivations": _roll_motivations(data)}


@app.get("/games")
async def games_page():
    return FileResponse(str(STATIC_DIR / "games.html"))


@app.get("/invite/{token}")
async def invite_page(token: str):
    return FileResponse(str(STATIC_DIR / "invite.html"))


@app.get("/play")
async def play():
    return FileResponse(str(STATIC_DIR / "play.html"))


@app.get("/engine-config")
async def engine_config_page():
    from starlette.responses import RedirectResponse
    return RedirectResponse("/my-engines", status_code=301)


@app.get("/my-engines")
async def my_engines_page():
    return FileResponse(str(STATIC_DIR / "my-engines.html"))


@app.get("/libraries")
async def libraries_page():
    from starlette.responses import RedirectResponse
    return RedirectResponse("/resources", status_code=301)


@app.get("/resources")
async def resources_page():
    return FileResponse(str(STATIC_DIR / "resources.html"))


@app.get("/login")
async def login_page():
    return FileResponse(str(STATIC_DIR / "login.html"))


def _get_changelog_hash() -> str:
    """Вычисляет хеш содержимого changelog."""
    if not CHANGELOG_FILE.exists():
        return ""
    content = CHANGELOG_FILE.read_text(encoding="utf-8")
    return hashlib.md5(content.encode()).hexdigest()


@app.get("/api/changelog/hash")
async def get_changelog_hash():
    """Возвращает хеш текущей версии changelog."""
    return {"hash": _get_changelog_hash()}


@app.get("/changelog")
async def changelog():
    if not CHANGELOG_FILE.exists():
        raise HTTPException(404, "changelog.html not found")
    return FileResponse(str(CHANGELOG_FILE))


@app.get("/{filepath:path}.md")
async def render_markdown(filepath: str):
    md_file = STATIC_DIR / f"{filepath}.md"
    if not md_file.exists() or not md_file.resolve().is_relative_to(STATIC_DIR.resolve()):
        raise HTTPException(404, "File not found")
    content = md_file.read_text(encoding="utf-8")
    html_body = markdown.markdown(content, extensions=["fenced_code", "tables", "codehilite"])
    title = filepath.split("/")[-1]
    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ max-width: 860px; margin: 40px auto; padding: 0 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #e0e0e0; background: #1a1a2e; }}
  h1, h2, h3 {{ color: #c9a84c; }}
  a {{ color: #6fa3ef; }}
  code {{ background: #16213e; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
  pre {{ background: #16213e; padding: 16px; border-radius: 8px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #333; padding: 8px 12px; text-align: left; }}
  th {{ background: #16213e; color: #c9a84c; }}
  blockquote {{ border-left: 4px solid #c9a84c; margin: 1em 0; padding: 0.5em 1em; color: #aaa; }}
  hr {{ border: none; border-top: 1px solid #333; }}
</style>
</head>
<body>{html_body}</body>
</html>"""
    return HTMLResponse(page)


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web_app:app", host="127.0.0.1", port=8000, reload=True, app_dir=str(RESOURCES_DIR))
