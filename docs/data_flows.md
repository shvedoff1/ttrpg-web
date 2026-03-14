## Потоки данных в проекте

### Источники данных

**1. База данных (SQLAlchemy/SQLite)** — хранит состояние:

| Таблица | Что хранит |
|---|---|
| `User` | email, username, google_id, password_hash |
| `Game` | название, slug, owner, settings (JSON) |
| `GameMember` | связь user↔game + роль (player/moderator/admin/owner) |
| `GameInvite` | токен приглашения, роль, срок действия |
| `GameEngine` | привязка движка к игре (system `engine_id` ИЛИ `user_engine_id`) |
| `UserEngine` | пользовательские движки (копия системного или композитный из примитивов) |
| `DataLibrary` | все JSON-данные, загруженные в БД по slug-ам |
| `GameLog` | журнал игры (data JSON + visibility public/admin) |

**2. JSON-файлы** (47 шт.) — исходные данные, **read-only при работе**:

| Тип (prefix slug) | Кол-во | Пример | Что внутри |
|---|---|---|---|
| `items.*` | 21 | `items.alchemy.herbs` | Каталоги предметов (name, price, probability) |
| `gen.*` | 8 | `gen.weapon.parts.bases` | Части/свойства для генерации предметов |
| `config.*` | 11 | `config.chest_game.default` | Конфиги движков (сундуки, воровство, торговцы и т.д.) |

### Главный поток: JSON → БД → Кэш → Движок

```
Старт приложения
  │
  ├─ Alembic миграции (создание таблиц)
  ├─ seed_libraries.py → загрузка 47 JSON в таблицу DataLibrary (owner_id=NULL)
  └─ _make_db_resolver() → кэш системных библиотек в памяти
```

### Поток при действии пользователя

```
Frontend: клик "Бросить кубик" в движке
  │
  ├─ POST /api/games/{id}/engines/{engine_id}/action
  │     {action: "roll", payload: {profession: "Травы", location: "forest"}}
  │
  ├─ Backend: загрузка GameEngine → резолв движка + конфига
  │     System: registry + default_config
  │     User (copy): base engine + custom_config (merge)
  │     User (composite): CompositeEngine + mechanics
  │
  ├─ Engine.handle_action() → load_json(slug)
  │     slug → _db_resolver → кэш/DataLibrary.data
  │     Расчёт (взвешенный рандом и т.п.)
  │     → возврат результата
  │
  ├─ Frontend получает результат
  │
  └─ POST /api/games/{id}/log → GameLog (visibility: public/admin)
       Все остальные получают через polling GET /api/games/{id}/log?after_id=N
```

### Ключевые особенности

- **JSON-файлы никогда не пишутся** — только читаются при старте и загружаются в `DataLibrary`
- **Системные библиотеки** (`owner_id=NULL`) — кэшируются в памяти, immutable
- **Пользовательские библиотеки** (`owner_id!=NULL`) — CRUD через API, без кэша, из БД напрямую
- **Slug-система** — единый механизм доступа к данным: `load_json("config.profession_roll.herbs")` — не важно, системная это библиотека или пользовательская
- **Журнал** — записи с visibility-фильтрацией: игроки видят только `public`, админы — всё
