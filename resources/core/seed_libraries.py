"""
core/seed_libraries.py — Сидирование системных DataLibrary из JSON-файлов.

Загружает все системные JSON-файлы в таблицу data_libraries при запуске.
Идемпотентно: вставляет новые, обновляет данные существующих системных библиотек.
"""

from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.models import DataLibrary

_JSONS_DIR = Path(__file__).parent.parent / "jsons"

# Маппинг: slug → (относительный путь от jsons/, lib_type, engine_id, name, description)
_LIBRARIES: list[tuple[str, str, str, str | None, str, str]] = [
    # (slug, path, lib_type, engine_id, name, description)

    # ── Item catalogs: алхимия ────────────────────────────────────────────────
    ("items.alchemy.herbs",    "resources/алхимия/herbs.json",    "item_catalog", None, "Травы",           "Алхимические травы"),
    ("items.alchemy.potions",  "resources/алхимия/potions.json",  "item_catalog", None, "Зелья",           "Алхимические зелья"),
    ("items.alchemy.reagents", "resources/алхимия/reagents.json", "item_catalog", None, "Реагенты",        "Алхимические реагенты"),

    # ── Item catalogs: охота ─────────────────────────────────────────────────
    ("items.hunt.arrows",   "resources/охота/arrows.json",   "item_catalog", None, "Стрелы",    "Охотничьи стрелы"),
    ("items.hunt.pelts",    "resources/охота/pelts.json",    "item_catalog", None, "Шкуры",     "Звериные шкуры"),
    ("items.hunt.traps",    "resources/охота/traps.json",    "item_catalog", None, "Ловушки",   "Охотничьи ловушки"),
    ("items.hunt.trophies", "resources/охота/trophies.json", "item_catalog", None, "Трофеи",   "Охотничьи трофеи"),

    # ── Item catalogs: провизия ───────────────────────────────────────────────
    ("items.food.alcohol", "resources/провизия/alcohol.json", "item_catalog", None, "Алкоголь", "Алкогольные напитки"),
    ("items.food.fish",    "resources/провизия/fish.json",    "item_catalog", None, "Рыба",     "Рыба и морепродукты"),
    ("items.food.food",    "resources/провизия/food.json",    "item_catalog", None, "Еда",      "Продовольствие"),
    ("items.food.spices",  "resources/провизия/spices.json",  "item_catalog", None, "Специи",   "Приправы и специи"),

    # ── Item catalogs: прочее ─────────────────────────────────────────────────
    ("items.misc.bags",        "resources/прочее/bags.json",        "item_catalog", None, "Сумки",       "Мешки и сумки"),
    ("items.misc.books",       "resources/прочее/books.json",       "item_catalog", None, "Книги",       "Книги и рукописи"),
    ("items.misc.candles",     "resources/прочее/candles.json",     "item_catalog", None, "Свечи",       "Свечи и осветительные предметы"),
    ("items.misc.cloth",       "resources/прочее/cloth.json",       "item_catalog", None, "Ткань",       "Ткани и материалы"),
    ("items.misc.curiosities", "resources/прочее/curiosities.json", "item_catalog", None, "Диковины",    "Редкие диковинные предметы"),
    ("items.misc.hardware",    "resources/прочее/hardware.json",    "item_catalog", None, "Скобяные",    "Скобяные изделия"),
    ("items.misc.hlam",        "resources/прочее/hlam.json",        "item_catalog", None, "Хлам",        "Разный мусор и хлам"),
    ("items.misc.locks",       "resources/прочее/locks.json",       "item_catalog", None, "Замки",       "Замки и ключи"),
    ("items.misc.loot",        "resources/прочее/loot.json",        "item_catalog", None, "Добыча",      "Случайная добыча"),
    ("items.misc.scrolls",     "resources/прочее/scrolls.json",     "item_catalog", None, "Свитки",      "Магические свитки"),
    ("items.misc.theft",       "resources/прочее/theft.json",       "item_catalog", None, "Воровство",   "Предметы для воровства"),
    ("items.misc.tools",       "resources/прочее/tools.json",       "item_catalog", None, "Инструменты", "Рабочие инструменты"),
    ("items.misc.wood",        "resources/прочее/wood.json",        "item_catalog", None, "Дерево",      "Древесина и деревянные изделия"),

    # ── Item catalogs: ремесло ───────────────────────────────────────────────
    ("items.craft.armor_parts", "resources/ремесло/armor_parts.json", "item_catalog", None, "Части доспехов", "Детали и части доспехов"),
    ("items.craft.gems",        "resources/ремесло/gems.json",        "item_catalog", None, "Самоцветы",      "Драгоценные камни"),
    ("items.craft.jewelry",     "resources/ремесло/jewelry.json",     "item_catalog", None, "Украшения",      "Ювелирные украшения"),
    ("items.craft.metal",       "resources/ремесло/metal.json",       "item_catalog", None, "Металл",         "Металлические изделия"),
    ("items.craft.ores",        "resources/ремесло/ores.json",        "item_catalog", None, "Руды",           "Металлические руды"),
    ("items.craft.weapons",     "resources/ремесло/weapons.json",     "item_catalog", None, "Оружие (сырьё)", "Оружие и заготовки"),

    # ── Generator parts ─────────────────────────────────────────────────────
    ("gen.weapon.parts.bases",     "generator/weapon/parts/bases.json",     "generator_parts", "item_generator", "Основы оружия",               "Базовые типы оружия для генератора"),
    ("gen.weapon.parts.materials", "generator/weapon/parts/materials.json", "generator_parts", "item_generator", "Материалы оружия",            "Материалы для генерации оружия"),
    ("gen.armor.parts.bases",      "generator/armor/parts/bases.json",      "generator_parts", "item_generator", "Основы брони",                "Базовые типы брони для генератора"),
    ("gen.armor.parts.materials",  "generator/armor/parts/materials.json",  "generator_parts", "item_generator", "Материалы брони",             "Материалы для генерации брони"),

    # ── Generator properties ─────────────────────────────────────────────────
    ("gen.weapon.props.positive", "generator/weapon/properties/positive.json", "generator_props", "item_generator", "Свойства оружия: позитивные", "Позитивные свойства генерируемого оружия"),
    ("gen.weapon.props.negative", "generator/weapon/properties/negative.json", "generator_props", "item_generator", "Свойства оружия: негативные", "Негативные свойства генерируемого оружия"),
    ("gen.armor.props.positive",  "generator/armor/properties/positive.json",  "generator_props", "item_generator", "Свойства брони: позитивные",  "Позитивные свойства генерируемой брони"),
    ("gen.armor.props.negative",  "generator/armor/properties/negative.json",  "generator_props", "item_generator", "Свойства брони: негативные",  "Негативные свойства генерируемой брони"),

    # ── Engine configs ───────────────────────────────────────────────────────
    ("config.chest_game.default",      "configs/chests_config.json",    "engine_config", "chest_game",       "Сундуки (стандарт)",          "Конфигурация типов сундуков и добычи"),
    ("config.trader.standard",         "configs/standard_traders.json", "engine_config", "trader_inventory", "Торговцы (стандарт)",         "Стандартные типы торговцев"),
    ("config.trader.named",            "configs/stores.json",           "engine_config", "trader_inventory", "Магазины (именные)",          "Именные магазины и их ассортимент"),
    ("config.item_gen.default",        "configs/item_generator.json",   "engine_config", "item_generator",   "Генератор предметов",         "Шаблоны генерации оружия и брони"),
    ("config.motivation.default",      "configs/motivations.json",      "engine_config", "story_motivation", "Мотивации персонажей",        "Список мотиваций для розыгрыша"),
    ("config.treasure.default",        "configs/treasure.json",         "engine_config", "treasure",         "Сокровища (стандарт)",        "Категории и веса сокровищ"),
    ("config.profession_roll.steal",   "configs/steal_config.json",     "engine_config", "profession_roll",  "Воровство: конфигурация",     "Параметры воровства по районам"),
    ("config.profession_roll.cache",   "configs/cache_config.json",     "engine_config", "profession_roll",  "Тайники: конфигурация",       "Параметры нахождения тайников"),
    ("config.profession_roll.herbs",   "configs/herb_locations.json",   "engine_config", "profession_roll",  "Травничество: локации",       "Веса трав по типам местности"),
    ("config.profession_roll.ores",    "configs/ore_locations.json",    "engine_config", "profession_roll",  "Горное дело: локации",        "Веса руд по типам местности"),
    ("config.profession_roll.trophies","configs/trophy_locations.json", "engine_config", "profession_roll",  "Охота: локации",              "Веса трофеев по типам местности"),
]

# Быстрый маппинг path → slug для обратной конвертации
PATH_TO_SLUG: dict[str, str] = {path: slug for slug, path, *_ in _LIBRARIES}


def _load_file(rel_path: str) -> dict | list:
    full = (_JSONS_DIR / rel_path).resolve()
    if not full.exists():
        return {}
    import json
    return json.loads(full.read_text(encoding="utf-8"))


def seed_libraries(db: Session) -> tuple[int, int]:
    """Вставляет новые и обновляет существующие системные библиотеки.

    Возвращает (added, updated).
    """
    added = 0
    updated = 0
    for slug, path, lib_type, engine_id, name, description in _LIBRARIES:
        exists = db.execute(
            select(DataLibrary).where(DataLibrary.slug == slug)
        ).scalar_one_or_none()

        data = _load_file(path)

        if exists:
            # Обновляем только системные (owner_id=NULL) если данные изменились
            if exists.owner_id is None and data and data != exists.data:
                exists.data = data
                updated += 1
            continue

        db.add(DataLibrary(
            slug=slug,
            name=name,
            description=description,
            lib_type=lib_type,
            engine_id=engine_id,
            owner_id=None,  # system
            is_public=True,
            data=data,
            source_slug=None,
        ))
        added += 1

    if added or updated:
        db.commit()

    return added, updated


def run_seed_libraries() -> None:
    """Точка входа: запускать при старте приложения."""
    db = SessionLocal()
    try:
        added, updated = seed_libraries(db)
        if added or updated:
            print(f"[seed_libraries] Добавлено {added}, обновлено {updated} системных библиотек")
    except Exception as exc:
        print(f"[seed_libraries] Ошибка: {exc}")
        db.rollback()
    finally:
        db.close()
