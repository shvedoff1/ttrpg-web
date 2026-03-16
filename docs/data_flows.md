## Потоки данных в проекте

### Источники данных

**1. База данных (SQLAlchemy/PostgreSQL)** — хранит состояние:

| Таблица | Что хранит |
|---|---|
| `User` | email, username, google_id, password_hash |
| `Game` | название, slug, owner, settings (JSON) |
| `GameMember` | связь user↔game + роль (player/moderator/admin/owner) |
| `GameInvite` | токен приглашения, роль, срок действия |
| `GameEngine` | привязка движка к игре (system `engine_id` ИЛИ `user_engine_id` ИЛИ `engine_category_id`) |
| `UserEngine` | пользовательские движки (копия системного или композитный из примитивов) |
| `EngineCategory` | категория — контейнер для группировки атомарных движков |
| `CategoryEngine` | атомарный движок внутри категории (1 примитив или 1 системный движок) |
| `ResourceItem` | единое хранилище предметов: key, name, price, weight, probability, meta, tags |
| `EngineResourceBinding` | привязка ресурсов к движку: tag_filter, role, item_overrides |
| `DataLibrary` | (legacy) JSON-данные по slug-ам — используется legacy-примитивами |
| `GameLog` | журнал игры (data JSON + visibility public/admin) |

**2. JSON-файлы** (47 шт.) — исходные данные, **read-only при работе**:

| Тип (prefix slug) | Кол-во | Пример | Что внутри |
|---|---|---|---|
| `items.*` | 21 | `items.alchemy.herbs` | Каталоги предметов (name, price, probability) |
| `gen.*` | 8 | `gen.weapon.parts.bases` | Части/свойства для генерации предметов |
| `config.*` | 11 | `config.chest_game.default` | Конфиги движков (сундуки, воровство, торговцы и т.д.) |

При старте предметы из JSON извлекаются в `resource_items` через `seed_resources.py`.

### Архитектура ресурсов (новая)

```
resource_items (единая таблица)
├── Системные (owner_id=NULL) — сидятся из JSON, read-only
├── Пользовательские (owner_id=user) — создаются или копируются
└── Теги вместо папок: ["alchemy", "herb"], ["craft", "gem"] и т.д.

engine_resource_bindings (привязка к движку)
├── tag_filter: ["alchemy", "herb"] — какие ресурсы подтянуть
├── role: "source" / "parts:base" / "props:positive" — роль для примитива
├── item_overrides: {"herb_3": {"probability": 20}} — delta overlay
└── priority, count, category_weight — параметры для pool_sample/cascade_roll
```

### Главный поток: JSON → ResourceItems → Bindings → Движок

```
Старт приложения
  │
  ├─ Alembic миграции (создание таблиц)
  ├─ seed_libraries.py → загрузка JSON в DataLibrary (legacy)
  ├─ seed_resources.py → извлечение предметов из JSON в resource_items
  └─ _make_db_resolver() → кэш системных библиотек в памяти (legacy)
```

### Поток при действии пользователя (новая система)

```
Frontend: клик "Бросить кубик" в движке
  │
  ├─ POST /api/games/{id}/categories/{ge_id}/engines/{ce_id}/action
  │     {action: "roll", payload: {context: "forest"}}
  │
  ├─ Backend: загрузка CategoryEngine → resolve primitive
  │     1. Загрузить config из category_engines.config
  │     2. resolve_bindings(engine_id) → EngineResourceBinding[]
  │     3. get_effective_items(binding) → resource_items по тегам + overrides
  │     4. Передать config + _bindings в primitive.execute()
  │
  ├─ Primitive.execute():
  │     Проверка config["_bindings"] → _execute_bindings() или _execute_legacy()
  │     _execute_bindings():
  │       Читает items из binding через get_effective_items()
  │       Читает contexts/filters/districts из engine config
  │       Расчёт (взвешенный рандом и т.п.)
  │     → возврат результата
  │
  ├─ Frontend получает результат
  │
  └─ POST /api/games/{id}/log → GameLog
```

### Delta Overlay (переопределения)

```python
def get_effective_items(binding, owner_id=None):
    """Загрузить предметы по тегам, применить оверрайды."""
    items = db.query(ResourceItem).filter(
        ResourceItem.tags.contains(binding.tag_filter),
        ResourceItem.owner_id == owner_id  # или NULL для системных
    ).all()

    overrides = binding.item_overrides or {}
    for item in items:
        if item.key in overrides:
            item.update(overrides[item.key])  # только изменённые поля
    return items
```

- Меняешь `price` у системного предмета → обновляется во всех движках
- Движок переопределил `probability` для `herb_3` → `price` обновится, `probability` нет

### Как примитивы используют привязки

| Примитив | Привязки (роли) | Engine config | На выходе |
|---|---|---|---|
| **weighted_roll** | 1× `source` | `show_price: bool` | Один предмет (name, price, weight) |
| **weighted_sample** | 1× `source` | `count: N`, `show_price: bool` | N предметов без повтора |
| **filtered_roll** | N× `source` | `filters: {district → rules}`, `show_price: bool` | Один предмет (name, price, weight) после фильтрации |
| **cascade_roll** | N× `source` (каждая = категория) | `category_weight`, `label`, `icon` в привязке, `show_price: bool` | Предмет (name, price, weight) + категория |
| **context_roll** | 1× `source` | `contexts: {loc → {name, overrides}}`, `show_price: bool` | Предмет (name, price, weight) с учётом локации |
| **loot_bundle** | N× `source` | `districts: {key → gold/items range}`, `show_price: bool` | Золото + массив предметов |
| **pool_sample** | N× `source` с priority+count | `objects_count: N`, `show_price: bool` | Инвентарь |
| **item_generator** | `parts:base`, `parts:material`, `props:positive`, `props:negative` | `templates: {type → config}` | Сгенерированный предмет |

### Ключевые особенности

- **Dual-mode**: все примитивы работают и через bindings (новое), и через legacy slug-конфиги
- **Системные ресурсы** (`owner_id=NULL`) — кэшируются, immutable для пользователей
- **Пользовательские ресурсы** (`owner_id!=NULL`) — CRUD через API, копируются из системных
- **Tag-система** — фильтрация по PostgreSQL GIN-индексу, заменяет папки и lib_type
- **Журнал** — записи с visibility-фильтрацией: игроки видят только `public`, админы — всё
- **Категории** — контейнеры для группировки атомарных движков

### API ресурсов

| Метод | URL | Назначение |
|---|---|---|
| `GET` | `/api/resources` | Список ресурсов (фильтр по тегам, owner, поиск) |
| `GET` | `/api/resources/tags` | Все уникальные теги |
| `GET` | `/api/resources/count` | Количество по тегам (превью) |
| `POST` | `/api/resources` | Создать ресурс |
| `POST` | `/api/resources/{id}/copy` | Копировать ресурс |
| `POST` | `/api/resources/bulk-copy` | Массовое копирование по тегам |
| `PATCH` | `/api/resources/{id}` | Обновить ресурс (owner only) |
| `DELETE` | `/api/resources/{id}` | Удалить ресурс (owner only) |

### API привязок

| Метод | URL | Назначение |
|---|---|---|
| `GET` | `/api/engines/{id}/bindings` | Список привязок движка |
| `POST` | `/api/engines/{id}/bindings` | Создать привязку |
| `PATCH` | `/api/bindings/{id}` | Обновить привязку |
| `DELETE` | `/api/bindings/{id}` | Удалить привязку |
| `POST` | `/api/engines/{id}/bindings/reorder` | Переупорядочить привязки |

### Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `resources/core/models.py` | Модели: ResourceItem, EngineResourceBinding, CategoryEngine и др. |
| `resources/core/seed_resources.py` | Seed: JSON → resource_items |
| `resources/engines/_helpers.py` | resolve_bindings(), get_effective_items(), load_json() |
| `resources/engines/primitives/*.py` | 7 примитивов (dual-mode: bindings + legacy) |
| `resources/routers/resources.py` | CRUD API для resource_items |
| `resources/routers/bindings.py` | CRUD API для engine_resource_bindings |
| `resources/routers/engines.py` | API движков |
| `resources/static/resources.html` | UI страница ресурсов |
| `resources/static/js/resources.js` | JS логика страницы ресурсов |
| `resources/static/js/engines/bindings-editor.js` | Визуальный редактор привязок |
| `resources/static/my-engines.html` | Страница «Категории» с интеграцией редактора привязок |
| `resources/web_app.py` | Главное приложение FastAPI |
