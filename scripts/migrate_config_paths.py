"""
scripts/migrate_config_paths.py — Конвертация путей к JSON-файлам в slug'и.

Рекурсивно заменяет строковые значения-пути в GameEngine.config на slug'и DataLibrary.
Запускать один раз после деплоя DataLibrary системы.

Использование:
  cd /Users/shvedovandrey/ttrpg-web/resources
  python ../scripts/migrate_config_paths.py
"""

import sys
from pathlib import Path

# Добавляем resources/ в путь
sys.path.insert(0, str(Path(__file__).parent.parent / "resources"))

from sqlalchemy import select
from core.database import SessionLocal
from core.models import GameEngine
from core.seed_libraries import PATH_TO_SLUG


def _deep_replace(obj: object) -> tuple[object, bool]:
    """Рекурсивно заменяет пути на slug'и. Возвращает (новый_объект, был_ли_изменён)."""
    if isinstance(obj, str):
        if obj in PATH_TO_SLUG:
            return PATH_TO_SLUG[obj], True
        return obj, False

    if isinstance(obj, list):
        changed = False
        result = []
        for item in obj:
            new_item, item_changed = _deep_replace(item)
            result.append(new_item)
            changed = changed or item_changed
        return result, changed

    if isinstance(obj, dict):
        changed = False
        result = {}
        for k, v in obj.items():
            new_v, v_changed = _deep_replace(v)
            result[k] = new_v
            changed = changed or v_changed
        return result, changed

    return obj, False


def migrate() -> None:
    db = SessionLocal()
    try:
        records = db.execute(select(GameEngine)).scalars().all()
        migrated = 0

        for rec in records:
            if not rec.config:
                continue
            new_config, changed = _deep_replace(rec.config)
            if changed:
                rec.config = new_config
                migrated += 1
                print(f"  [game_engine id={rec.id}] config обновлён")

        if migrated:
            db.commit()
            print(f"\nМигрировано {migrated} записей GameEngine.")
        else:
            print("Нечего мигрировать — все конфиги уже используют slug'и или пустые.")

    except Exception as exc:
        print(f"Ошибка: {exc}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Миграция GameEngine.config: пути → slug'и...")
    migrate()
