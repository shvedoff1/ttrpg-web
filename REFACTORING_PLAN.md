# План рефакторинга TTRPG-Web
_Составлен: 2026-03-13_

---

## Текущее состояние

- FastAPI + Vanilla JS, без БД (JSON-файлы)
- Одна игра ("Готика") — захардкоженная логика
- Авторизация — только имя в cookie, без пароля
- Нет ролей, нет многопользовательских сессий

---

## Цели рефакторинга

### 1. Мультидвижковая платформа

Превратить сервис из приложения под одну игру в платформу, где:
- Каждая **игра (game)** — это набор конфигурируемых движков (engines)
- **Движок (engine)** — плагинообразная единица функциональности (пример текущих: profession rolls, chest mini-game, item generator, trader inventory)
- Создатель игры выбирает/конфигурирует движки и настраивает данные (JSON или БД)
- Движки могут иметь собственный набор JSON-конфигов, загруженных через UI

**Что это означает для архитектуры:**
- Абстракция `Engine` с интерфейсом: `init(config)`, `handle_action(payload)`, `get_ui_meta()`
- Реестр движков на бэке — каждый движок регистрируется с уникальным `engine_id`
- Каждая игра хранит список подключённых движков + их конфигурации
- Текущая логика Готики превращается в набор движков (первые в реестре)

**Примеры встроенных движков:**
| engine_id | Описание |
|---|---|
| `profession_roll` | Взвешенный ролл по локации/профессии |
| `chest_game` | Мини-игра с последовательностью направлений |
| `item_generator` | Генератор предметов из частей и свойств |
| `trader_inventory` | Инвентарь торговцев с кешированием |
| `story_motivation` | Случайные мотивации персонажей |

---

### 2. Нормальная авторизация

Заменить cookie с именем на полноценную систему:

**Методы входа:**
- Логин + пароль (bcrypt хэширование)
- OAuth через Google (google-auth / authlib)

**Механизм сессий:**
- JWT токены (access + refresh) вместо cookie с именем
- `access_token`: короткоживущий (15 мин)
- `refresh_token`: долгоживущий (30 дней), хранится в httpOnly cookie

**Что нужно сделать:**
- Таблица `users` в БД (id, email, username, password_hash, google_id, created_at)
- Эндпоинты: `POST /auth/register`, `POST /auth/login`, `POST /auth/google`, `POST /auth/refresh`, `POST /auth/logout`
- Текущий `auth.py` — переписать полностью

---

### 3. Ролевая модель на уровне игр

**Флоу:**
1. Пользователь регистрируется/логинится
2. Создаёт **игру** (game): задаёт название, подключает движки, загружает конфиги
3. Получает ссылку-приглашение (инвайт) для друзей
4. Друзья принимают инвайт и вступают в игру
5. Создатель назначает роли каждому участнику

**Роли (на уровне игры):**
| Роль | Права |
|---|---|
| `owner` | Всё, включая удаление игры и управление движками |
| `admin` | Управление участниками, конфигами движков, логами |
| `moderator` | Запуск роллов, управление контентом (JSON), сброс кешей |
| `player` | Только запуск роллов, просмотр результатов |

**Схема данных:**
```
users: id, email, username, password_hash, google_id, created_at
games: id, name, slug, owner_id, created_at, settings (JSONB)
game_engines: id, game_id, engine_id, config (JSONB), order
game_members: id, game_id, user_id, role, joined_at
game_invites: id, game_id, token, created_by, role, expires_at, used_at
```

---

### 4. Сохранение текущего функционала

Вся логика Готики сохраняется, но перемещается в движки:

**Текущие файлы → новые модули:**
| Файл | Новое место |
|---|---|
| `web_app.py` (логика роллов) | `engines/profession_roll.py` |
| `chest_game_api.py` | `engines/chest_game.py` |
| `item_generator.py` | `engines/item_generator.py` |
| `auth.py` | `core/auth.py` (переписан) |
| `resources/jsons/` | остаётся как дефолтные конфиги движков |

**БД vs JSON:**
- JSON-файлы сохраняются как источник данных для движков
- БД используется только для: пользователей, игр, ролей, инвайтов, логов
- Движки могут читать как из JSON (файлов), так и из БД — через адаптер источника данных

---

## Технический стек

| Компонент | Текущее | Новое |
|---|---|---|
| Backend | FastAPI | FastAPI (сохраняем) |
| БД | - | PostgreSQL (или SQLite для dev) |
| ORM | - | SQLAlchemy 2.x + Alembic |
| Auth | cookie с именем | JWT + Google OAuth |
| Пароли | - | bcrypt / passlib |
| Frontend | Vanilla JS | Vanilla JS (сохраняем, расширяем) |

---

## Этапы реализации

### Этап 0: Подготовка ✅ _выполнен 2026-03-13_
- [x] Выбрать БД — SQLite (dev), легко сменить на PostgreSQL через `DATABASE_URL`
- [x] Настроить SQLAlchemy 2.x + Alembic (`alembic/`, `alembic.ini`, `resources/core/database.py`)
- [x] Создать базовые таблицы (`users`, `games`, `game_members`, `game_invites`, `game_engines`) — миграция `c4be1ed24337`

### Этап 1: Авторизация
- [ ] Таблица `users`
- [ ] Эндпоинты login/register с JWT
- [ ] Google OAuth
- [ ] Middleware для защиты роутов

### Этап 2: Игры и роли
- [ ] CRUD для игр (`POST /api/games`, `GET /api/games`, etc.)
- [ ] Система инвайтов (`POST /api/games/{id}/invite`)
- [ ] Управление ролями (`PATCH /api/games/{id}/members/{user_id}`)
- [ ] Middleware проверки ролей

### Этап 3: Движки (engines)
- [ ] Абстракция `BaseEngine`
- [ ] Реестр движков
- [ ] Перенос текущей логики в отдельные движки
- [ ] API для подключения движков к игре
- [ ] UI для выбора и настройки движков

### Этап 4: UI обновление
- [ ] Страница создания игры
- [ ] Страница управления игрой (участники, роли, движки)
- [ ] Страница принятия инвайта
- [ ] Обновление play.html/admin.html под мультигейм-контекст
- [ ] Обновление auth UI (форма логина/регистрации + кнопка Google)

### Этап 5: Миграция данных
- [ ] Текущие JSON конфиги → дефолтные конфиги движков для первой игры "Готика"
- [ ] Тестирование что весь старый функционал работает

---

## Структура проекта (целевая)

```
ttrpg-web/
├── resources/
│   ├── core/
│   │   ├── auth.py           # JWT, Google OAuth
│   │   ├── database.py       # SQLAlchemy setup
│   │   ├── models.py         # ORM модели
│   │   └── permissions.py    # Ролевые проверки
│   ├── engines/
│   │   ├── base.py           # BaseEngine абстракция
│   │   ├── registry.py       # Реестр движков
│   │   ├── profession_roll.py
│   │   ├── chest_game.py
│   │   ├── item_generator.py
│   │   ├── trader_inventory.py
│   │   └── story_motivation.py
│   ├── routers/
│   │   ├── auth.py           # /auth/*
│   │   ├── games.py          # /api/games/*
│   │   ├── engines.py        # /api/engines/*
│   │   └── files.py          # /api/files/* (JSON editor)
│   ├── web_app.py            # FastAPI app, монтирование роутеров
│   ├── static/               # Frontend
│   └── jsons/                # Дефолтные конфиги движков
├── alembic/                  # Миграции БД
├── requirements.txt
└── REFACTORING_PLAN.md       # Этот файл
```

---

## Открытые вопросы

1. **БД**: SQLite (проще, меньше инфра) или PostgreSQL (лучше для prod)?
2. **Frontend**: оставаться на Vanilla JS или добавить лёгкий фреймворк (Alpine.js, Preact)?
3. **Движки**: разрешать пользователям загружать собственный Python-код движка или только JSON-конфиги?
4. **Логи**: хранить в БД или оставить в JSON-файле `log.json`?
5. **Первый релиз**: начать с Этапа 1 (Auth) и Этапа 2 (Игры/Роли) до рефакторинга движков?
