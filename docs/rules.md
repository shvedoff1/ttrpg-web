# Логика выборов на странице Play


## Общая архитектура

Страница Play использует **трёхуровневую систему выборов**:

1. **Уровень 1** — Выбор категории (основная тема)
2. **Уровень 2** — Выбор профессии / подкатегории
3. **Уровень 3** — Выбор локации / параметра

После выборов пользователь нажимает кнопку **«⚔ Ищем»** — фронт делает `POST /api/play/roll`, бек выполняет ролл на сервере и возвращает результат. Никакие JSON-файлы напрямую по сети не передаются.

**Разделение ответственности:**
- **Фронт** (`play.js`) — UI-состояние, рендер кнопок, отображение результата, логирование
- **Бек** (`web_app.py`) — чтение JSON-файлов, вся логика ролла, API

---

## Состояние (state, play.js)

```js
let activeCat        = null;  // Выбранная категория (Профессии / Предметы / Сюжет)
let activeProfession = null;  // { name, source, icon }
let activeParam1     = null;  // { key, name, icon } — первый шаг для режима multi
let activeLocation   = null;  // { name, locationKey?, param1Key?, param2Key?, subtype?, key? }
```

`activeLocation` больше не хранит функцию `roll()` — только параметры для передачи в `/api/play/roll`.

---

## API-эндпоинты (web_app.py)

| Метод | URL | Назначение |
|-------|-----|-----------|
| `GET` | `/api/play/profession/{name}/locations` | Список локаций для профессии |
| `GET` | `/api/play/traders/named` | Список именных торговцев |
| `GET` | `/api/play/traders/inventory/{subtype}/{key}` | Инвентарь торговца (кешируется) |
| `GET` | `/api/generate/weapon?subtype=sword&count=5` | Генерировать N оружий |
| `GET` | `/api/generate/armor?subtype=heavy&count=3` | Генерировать N комплектов брони |
| `POST` | `/api/play/roll` | Выполнить ролл, вернуть результат |
| `POST` | `/api/play/chest-start` | Начать игру в сундук, получить game_id |
| `POST` | `/api/play/chest-guess` | Угадать направление в игре сундука |
| `POST` | `/api/play/story/motivation` | Получить 3 случайных мотивации |
| `POST` | `/api/admin/reset-traders-cache` | Сброс кеша инвентаря торговцев |

---

## Категории первого уровня

### ⚔ Профессии

#### 🌿 Травы / ⛏ Руды / 🐾 Следы
- **Режим**: `with_locations`
- **Данные на беке**: `resources/{категория}/{type}.json` + `configs/{type}_locations.json`

**Поток:**
1. Клик на профессию → фронт делает `GET /api/play/profession/{name}/locations`
2. Бек читает файл локаций, возвращает `[{ key, name }]`
3. Фронт рендерит кнопки локаций
4. Выбор локации → `activeLocation = { name, locationKey: loc.key }`
5. «⚔ Ищем» → `POST /api/play/roll` с `{ type: "profession", profession, location: locationKey }`
6. Бек: читает `{type}.json` + `{type}_locations.json`, берёт `overrides` выбранной локации, выполняет взвешенный ролл (`_roll_with_locations`)
7. Возвращает `{ name, price }`

**Логика `_roll_with_locations`**: `overrides` локации — словарь `{ item_id: weight }`. Доступны только предметы из `overrides`, вес берётся оттуда же.

#### 🗝 Воровство
- **Режим**: `multi` (двухшаговый)
- **Данные на беке**: `configs/steal_config.json` (карманная кража), `configs/cache_config.json` (схрон)
- **Шаг 1 — `param1`** (hardcoded на фронте):
  - 📦 `cache` — Поиск схрона
  - ✋ `steal` — Карманная кража
- **Шаг 2 — `param2`** (hardcoded на фронте):
  - 🏚 `poor` — Бедный район
  - 🏘 `normal` — Обычный район
  - 🏛 `rich` — Богатый район
  - 🔮 `magic` — Обитель магии

**Поток:**
1. Клик на Воровство → рендер кнопок param1 из `PROFESSION_SOURCES` (без запроса к беку)
2. Выбор param1 → рендер кнопок param2 (тоже без запроса)
3. Выбор param2 → `activeLocation = { name, param1Key, param2Key }`
4. «⚔ Ищем» → `POST /api/play/roll` с `{ type: "profession", profession: "Воровство", param1, param2 }`
5. Бек: читает соответствующий конфиг (`steal_config.json` или `cache_config.json`), выполняет ролл
6. Возвращает `{ name }` (кража) или `{ gold, items[] }` (схрон)

---

### 🗝 Механика карманной кражи (`steal_config.json`)

Всегда возвращает **1 предмет** из пула категорий, указанных в конфиге.

**Фильтрация по району** (`district_filter`):

| Район | filter | percent | Эффект |
|-------|--------|---------|--------|
| `poor` | `exclude_rarest` | 75 | Убирает 75% предметов с наименьшим `probability` |
| `normal` | `exclude_rarest` | 20 | Убирает 20% предметов с наименьшим `probability` |
| `rich` | `exclude_common` | 20 | Убирает 20% предметов с наибольшим `probability` |
| `magic` | `exclude_common` | 20 | Убирает 20% предметов с наибольшим `probability` |

**Алгоритм фильтрации:**
1. Собрать все предметы из всех указанных в `categories` файлов
2. Отсортировать по `probability`
3. `exclude_rarest N%` → убрать нижние N% (самые редкие)
4. `exclude_common N%` → убрать верхние N% (самые частые)
5. Взвешенный ролл по оставшимся, вес = `probability`

**Категории** (что носят с собой): провизия/food, провизия/alcohol, провизия/spices, прочее/tools, прочее/hardware, прочее/locks, прочее/cloth, прочее/bags, прочее/candles, ремесло/jewelry, ремесло/gems, алхимия/potions, прочее/scrolls, алхимия/reagents, прочее/books, прочее/curiosities, прочее/hlam

---

### 📦 Механика схрона (`cache_config.json`)

Возвращает **золото + несколько предметов** из пула категорий.

| Район | gold_min | gold_max | items_min | items_max | Исключения |
|-------|---------|---------|---------|---------|-----------|
| `poor` | 0 | 50 | 1 | 3 | gems, jewelry |
| `normal` | 50 | 150 | 2 | 4 | — |
| `rich` | 150 | 500 | 3 | 5 | hlam |

**Алгоритм:**
1. Золото: случайное число от `gold_min` до `gold_max`
2. Количество предметов: случайное от `items_min` до `items_max`
3. Для каждого предмета: ролл из объединённого пула категорий по `probability`

---

### 🎒 Предметы

#### 🏪 Торговцы
- **Режим**: `traders`
- **Шаг 1** — тип: Стандартные / Именные

**Конфигурация торговцев** (единая структура для всех):

Все торговцы (стандартные и именные) определяются в JSON с полями:
- `name` — имя с иконкой
- `coefficient` — коэффициент цены (по умолчанию 1.5)
- `objects_count` — максимальное количество товаров в инвентаре (null = без лимита)
- `categories` — массив категорий товаров
- `resources_override` — (только именные) уникальные предметы

**Структура категории:**
```json
{
  "resource_file": "resources/алхимия/potions.json",
  "count": 6,
  "priority": 2
}
```
- `resource_file` — путь к файлу ресурсов (взаимоисключающе с `generate`)
- `generate` — тип генерируемого предмета (напр. `"weapon"` или `"armor"`) — вместо `resource_file`
- `subtype` — подтип при использовании `generate` (напр. `"sword"`, `"heavy"`)
- `count` — количество предметов из этого файла или генерирую (используется при объединении с max слотов)
- `priority` — приоритет (больше = выше)

**Стандартные** (файл `configs/standard_traders.json`):
- ⚔ Оружейник
- 🛡 Бронник
- 🐾 Охотник
- 🌿 Травник
- ⚗ Алхимик
- 🧵 Галантерейщик
- 💎 Ювелир
- 🍺 Еда и напитки

**Именные** (файл `configs/stores.json`):
- Кантар, Странствующий торговец, Долабеб, и др.
- Имеют `resources_override` для уникальных предметов
- Список именных → `GET /api/play/traders/named` (бек читает `stores.json`)

**Алгоритм формирования инвентаря:**

Если `objects_count = null` — вычисляется как `sum(count)` из всех категорий.

Применяется приоритизация:
1. Группируем категории по `priority` (убывание)
2. Для каждого уровня приоритета:
   - Объединяем все resource_file этого уровня в один пул
   - Считаем сумму `count` в группе
   - `take = min(оставшихся_слотов, sum_count)`
   - Рандомим `take` предметов из пула (взвешенный ролл по `probability`, без повторов)
3. Переходим к следующему приоритету до заполнения всех слотов

**Поток (любой торговец):**
1. Выбор торговца → `GET /api/play/traders/inventory/{subtype}/{key}`
2. Бек проверяет кеш по ключу `{subtype}:{key}`:
   - Если есть в кеше — возвращает кешированный результат
   - Если нет — вызывает `_build_trader_inventory()`:
     - Группирует категории по приоритету
     - Рандомит товары согласно `objects_count` и приоритетам
     - Применяет `coefficient` к ценам
     - Сортирует по `probability`, возвращает `{ items: [{name, price, unique}] }`
     - **Кеширует результат**
3. Фронт рендерит список инвентаря. Кнопка «Ищем» **скрыта** — торговцы только показывают инвентарь, ролл не выполняется.

**Кеширование инвентаря:**
- Каждый торговец генерируется один раз и кешируется на сервере в памяти
- При повторном открытии того же торговца выдаётся кешированный список
- Сброс кеша: кнопка **🔄 Сброс кеша** в админке (`/admin`) → `POST /api/admin/reset-traders-cache`

#### 💎 Сокровища
- **Режим**: `treasure`
- **Данные на беке**: `configs/treasure.json`
- **Кнопка** меняется на «💎 Найти», активна сразу (локация не выбирается)
- `activeLocation = { name: 'Сокровище' }`

**Поток:**
1. Клик на Сокровища → кнопка «💎 Найти» активна
2. «💎 Найти» → `POST /api/play/roll` с `{ type: "treasure" }`
3. Бек: двухуровневый ролл — сначала категория по `weight`, затем предмет по `probability` из файла ресурсов (`_roll_treasure`)
4. Возвращает `{ name, price, category }`

**Структура `treasure.json`:**
- `categories.{key}` — `{ label, icon, weight, resource_file }`
  - `weight` — вес категории (зелье: 40, оружие: 30, свиток: 30)
  - `resource_file` — путь к файлу с ресурсами (например, `resources/алхимия/potions.json`)

#### 📦 Сундуки (с мини-игрой)
- **Режим**: `chests`
- **Данные на беке**: `configs/chests_config.json`, `chest_game_api.py`
- **Шаг 1** — тип сундука (hardcoded на фронте):
  - 📦 `common` — Обычный деревянный сундук
  - 🗃 `metal` — Сундук с металлической оковкой
  - 🔒 `special` — Особое хранилище
  - ✨ `magic` — Магический сундук

**Мини-игра — угадай последовательность направлений:**

Для каждого типа сундука задана последовательность N направлений (↑↓←→) в конфиге:
```json
"game": {
    "length": 3,
    "directions": ["up", "down", "left", "right"]
}
```

**Поток:**
1. Клик на Сундуки → рендер кнопок типов
2. Выбор типа → скрыта кнопка «🗝 Открыть», показана игра с 4 кнопками направлений
3. На бек: `POST /api/play/chest-start` → бек генерирует случайную последовательность, возвращает `{ game_id, length }`
4. Фронт отображает слоты прогресса (X/N угадано) и кнопки ↑↓←→
5. Юзер угадывает направления → `POST /api/play/chest-guess` с `{ game_id, direction }`
   - Если верно: открыть слот с иконкой направления, перейти на следующий
   - Если неверно: увеличить счетчик попыток
6. После угадывания всей последовательности: `POST /api/play/chest-guess` вызывает `_roll_cache`, возвращает `{ correct: true, done: true, result: { name, gold, items[] }, attempts }`
7. Показать результат (золото + предметы), логирование включает счетчик попыток

**Механика сундука**: аналогична схронам — золото + предметы из пула категорий по `probability`.

| Тип | gold_min | gold_max | items_min | items_max | Особенности |
|-----|---------|---------|---------|---------|------------|
| `common` | 0 | 25 | 1 | 2 | Только базовые категории |
| `metal` | 20 | 80 | 2 | 3 | Все кроме gems, jewelry |
| `special` | 80 | 300 | 3 | 5 | Все кроме hlam |
| `magic` | 50 | 250 | 2 | 4 | Акцент на зелья/свитки/самоцветы |

---

### 📜 Сюжет

Все три раздела открывают `interactArea` с кнопкой **«🎲 Зароллить»** — локация не выбирается, `activeLocation` выставляется сразу.
Логика ролла живёт в `doStoryRoll(mode)`, который вызывается из `doSearch()` при `mode` из семейства `story_*`.

#### 🎭 Мотивация
- **Режим**: `story_motivation`
- **Данные**: `configs/motivations.json` — массив `{ name, weight }`
- **Поток:**
  1. Клик → кнопка «🎲 Зароллить» активна
  2. `POST /api/play/story/motivation` (без тела)
  3. Бек вызывает `_roll_motivations(data, 3)` — взвешенный ролл без повторов, возвращает `{ motivations: ["...", "...", "..."] }`
  4. Фронт отображает 3 мотивации в блоке `traderInventory` (аналог инвентаря торговца)

**Логика `_roll_motivations(data, count=3)`**: на каждой итерации взвешенный ролл по оставшимся вариантам, выбранный удаляется из пула → 3 уникальных результата.

#### ⚡ Событие
- **Режим**: `story_event`
- **Статус**: заглушка — рандомит число от 1 до 10 на фронте
- **Поток:**
  1. Клик → кнопка «🎲 Зароллить» активна
  2. Клик → `Math.floor(Math.random() * 10) + 1`, результат в попапе

#### 🗡 Дозор
- **Режим**: `story_patrol`
- **Статус**: заглушка — рандомит число от 1 до 10 на фронте
- **Поток:** аналогично ⚡ Событию

---

## 🎰 Генерация оружия и брони

Инкапсулированный модуль (`item_generator.py`) для процедурной генерации оружия и брони.

### Структура предмета

Каждый сгенерированный предмет состоит из **двух категорий частей** + **свойств**:

1. **Основа** — определяет тип предмета
   - Для оружия: Меч, Кинжал, Топор, Булава, Копьё, Лук, Двуручный меч
   - Для брони: Лёгкая, Средняя, Тяжёлая, Пластинчатая, Чешуйчатая, Кожаная, Кольчуга

2. **Материал** — из чего сделан предмет
   - 8 типов: Железо, Сталь, Бронза, Серебро, Мифрил, Магическая сталь, Орочья сталь, Адамантит/Драконья чешуя

3. **Свойства** — позитивные и негативные
   - Позитивные: Острое, Сбалансированное, Зачарованное, Укреплённое, Отравленное, Огненное (оружие)
   - Позитивные: Укреплённая, Зачарованная, Гибкая, Устойчивая, Благословённая, Непробиваемая (броня)
   - Негативные: Тяжёлое, Тупое, Хрупкое, Проклятое, Несбалансированное (оружие)
   - Негативные: Тяжёлая, Ограничивающая, Заржавленная, Повреждённая, Проклятая, Тесная (броня)

### Цена

Рассчитывается как: `цена_основы + цена_материала + сумма_цен_свойств` (свойства могут иметь отрицательную цену).

Минимальная цена = 0 (не может быть ниже).

### Конфигурация

**Файл**: `configs/item_generator.json`

Определяет для каждого типа (оружие/броня) и подтипа (sword/heavy):
- Список категорий частей (основа, материал) с путями к JSON файлам
- Группы свойств (позитивные, негативные) с количеством (min/max)

```json
{
  "weapon": {
    "sword": {
      "name": "Меч",
      "parts": [
        {"slot": "base", "name": "Основа", "source": "generator/weapon/parts/bases.json"},
        {"slot": "material", "name": "Материал", "source": "generator/weapon/parts/materials.json"}
      ],
      "property_groups": [
        {"name": "Позитивные", "source": "generator/weapon/properties/positive.json", "count_min": 1, "count_max": 2},
        {"name": "Негативные", "source": "generator/weapon/properties/negative.json", "count_min": 0, "count_max": 1}
      ]
    }
  }
}
```

### Интеграция с торговцами

Торговцы, которые генерируют предметы (⚔ Оружейник, 🛡 Бронник), используют в конфиге вместо `resource_file`:

```json
{
  "generate": "weapon",
  "subtype": "sword",
  "count": 5,
  "priority": 2
}
```

Остальная логика (`_build_trader_inventory`, кеширование) работает как для обычных предметов.

### API endpoints для прямой генерации

- `GET /api/generate/weapon?subtype=sword&count=5` — генерировать 5 мечей
- `GET /api/generate/armor?subtype=heavy&count=3` — генерировать 3 комплекта брони

### Структура ответа API

Сгенерированный предмет в инвентаре торговца:
```json
{
  "name": "Меч, сталь",
  "price": 240,
  "unique": false,
  "parts": ["Меч", "сталь"],
  "properties": ["Острое", "Сбалансированное", "Тяжёлое"]
}
```

Обычные предметы имеют `parts: null` и `properties: null`.

---

## Логика ролла (бек, web_app.py)

### `_roll_weighted(resources)`
```
Вход:  { "название": вес, ... }
Выход: { name }
```
Воровство.

### `_roll_with_locations(items, location)`
```
Вход:  items dict, location с полем overrides
Выход: { name, price }
```
Травы / Руды / Следы. Только предметы из `overrides` доступны в локации.

### `_roll_treasure(data)`
```
Вход:  treasure.json
Выход: { name, price, category }
```
Двухшаговый: категория → предмет.

### `_sample_weighted(entries, count)`
```
Вход:  список предметов, количество для выборки
Выход: список выбранных предметов (без повторов)
```
Взвешенная выборка без замены. Используется при формировании инвентаря торговца с ограничением по слотам.

### `_build_trader_inventory(categories, objects_count)`
```
Вход:  категории с { resource_file, count, priority } ИЛИ { generate, subtype, count, priority }, max слотов (или null)
Выход: объединённый pool предметов
```
Формирует инвентарь торговца по приоритетам. Если `objects_count = null`, вычисляет как sum(count).

Для каждой категории:
- Если есть `resource_file` — загружает предметы из JSON файла
- Если есть `generate` — вызывает `generate_items(category, subtype, count)` из модуля `item_generator`

Рандомит нужное количество предметов из каждой группы приоритетов (от высшего к низшему).

### `generate_items(category, subtype, count)` (item_generator.py)
```
Вход:  категория ("weapon" или "armor"), подтип ("sword", "heavy"), количество
Выход: список предметов [{ name, price, probability, parts, properties }, ...]
```
Генерирует `count` предметов заданного типа с использованием конфига `item_generator.json`:
- Для каждого предмета выбирает одну часть из каждого слота (основа, материал) по вероятности
- Для каждой группы свойств выбирает случайное количество (от count_min до count_max) свойств
- Рассчитывает итоговую цену (основа + материал + свойства)
- Собирает имя как конкатенацию: "Основа, материал"

### `_roll_merged_items(pool, coefficient)`
```
Вход:  объединённый pool, коэффициент цены
Выход: { name, price }
```
Торговцы (вызывается не через `/api/play/roll`, а только для inventory).

---

## Поток данных (пример: сбор трав)

1. Пользователь выбирает **Профессии → Травы**
2. `GET /api/play/profession/Травы/locations` → бек читает `configs/herb_locations.json`, возвращает `[{key, name}]`
3. Фронт рендерит 6 кнопок локаций
4. Пользователь выбирает **Лесные** → `activeLocation = { name: "Лесные", locationKey: "type2" }`
5. «⚔ Ищем» → `POST /api/play/roll` с `{ type: "profession", profession: "Травы", location: "type2" }`
6. Бек: читает `resources/алхимия/herbs.json` + `configs/herb_locations.json`, берёт `overrides` локации, выполняет взвешенный ролл
7. Возвращает `{ name: "Зверобой", price: 12 }`
8. Фронт показывает попап и логирует: «🌿 Травы · Лесные · 14:32:15 · Зверобой»

---

## Логирование

После каждого ролла `doSearch()` делает `POST /api/log`:
```json
{ "profIcon": "🌿", "profName": "Травы", "locName": "Лесные", "result": {...}, "time": "14:32:15" }
```
Лог хранится в `log.json` (макс. 500 записей), другие клиенты читают его через `GET /api/log?after={offset}` (поллинг каждые 5 сек).

---

## Структура JSON-файлов

```
resources/jsons/
  configs/                        ← конфиги поведения
    steal_config.json             Конфиг карманной кражи
    cache_config.json             Конфиг схрона
    chests_config.json            Конфиг сундуков
    treasure.json                 Категории и веса сокровищ
    standard_traders.json         Стандартные торговцы (8 шт)
    stores.json                   Именные торговцы
    motivations.json              Мотивации персонажа
    item_generator.json           Конфиг генерации оружия и брони
    herb_locations.json           Overrides трав по локациям
    ore_locations.json            Overrides руд по локациям
    trophy_locations.json         Overrides трофеев по локациям
  generator/                      ← файлы для генерации оружия и брони
    weapon/
      parts/
        bases.json                Типы оружия (меч, кинжал, топор и т.д.)
        materials.json            Материалы для оружия
      properties/
        positive.json             Позитивные свойства оружия
        negative.json             Негативные свойства оружия
    armor/
      parts/
        bases.json                Типы брони (лёгкая, средняя и т.д.)
        materials.json            Материалы для брони
      properties/
        positive.json             Позитивные свойства брони
        negative.json             Негативные свойства брони
  resources/                      ← предметы по категориям
    ремесло/                      weapons, armor_parts, ores, metal, gems, jewelry
    охота/                        arrows, traps, pelts, trophies
    алхимия/                      herbs, potions, reagents
    провизия/                     food, alcohol, spices, fish
    прочее/                       wood, scrolls, tools, hardware, locks, cloth,
                                  bags, candles, books, curiosities, hlam, theft, loot
```

## Ключевые файлы

| Файл | Назначение |
|------|-----------|
| `resources/static/play.html` | Рендер кнопок, панелей, попапа, лога |
| `resources/static/play.js` | UI-состояние, рендер, вызовы API |
| `resources/static/play.css` | Готическое оформление |
| `resources/static/chest_game.js` | Логика мини-игры сундуков (чистая инкапсуляция) |
| `resources/static/chest_game.css` | Стили игры: слоты, кнопки направлений, прогресс |
| `resources/web_app.py` | Все API: ролл, локации, инвентарь, лог |
| `resources/chest_game_api.py` | API эндпоинты для мини-игры сундуков (APIRouter) |
| `resources/item_generator.py` | Генерация оружия и брони (инкапсулированный модуль) |
| `resources/jsons/configs/item_generator.json` | Конфиг типов оружия/брони (части, свойства, количества) |
| `resources/jsons/configs/herb_locations.json` | Overrides трав по локациям |
| `resources/jsons/configs/ore_locations.json` | Overrides руд по локациям |
| `resources/jsons/configs/trophy_locations.json` | Overrides трофеев по локациям |
| `resources/jsons/configs/steal_config.json` | Конфиг карманной кражи: категории + фильтры по районам |
| `resources/jsons/configs/cache_config.json` | Конфиг схрона: золото/предметы по районам |
| `resources/jsons/configs/chests_config.json` | Конфиг сундуков: золото/предметы по типу сундука |
| `resources/jsons/configs/treasure.json` | Категории и веса сокровищ |
| `resources/jsons/configs/standard_traders.json` | Стандартные торговцы (категории, приоритеты, лимиты) |
| `resources/jsons/configs/stores.json` | Именные торговцы (категории, приоритеты, уникальные предметы) |
| `resources/jsons/configs/motivations.json` | Мотивации персонажа с весами |
