docker compose down
docker compose build --no-cache app
docker compose up -d mysql phpmyadmin
docker compose up -d app
docker compose logs -f app


# TWAP Telegram Parser


Python-сервис для чтения Telegram-каналов через пользовательское Telegram App API (`api_id` / `api_hash`), парсинга TWAP-сообщений, фильтрации, сохранения в MySQL и пересылки принятых сигналов в целевой чат/топик.

## Стек

- Python 3.12
- Telethon
- MySQL 8.4
- phpMyAdmin
- Docker Compose

## Что нужно заполнить

Скопировать `.env.example` в `.env` и заполнить:

```env
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
```

Уже выставленные значения для первой группы:

```env
TWAPX_SOURCE_CHAT_IDS=-1003663170785
TWAPX_SOURCE_THREAD_IDS=
TWAPX_SOURCE_CHAT_THREADS=
TWAPX_TARGET_CHAT_ID=-1003918218733
TWAPX_TARGET_THREAD_ID=4
```

Фильтр по умолчанию:

```env
TWAPX_MIN_USD=300000
TWAPX_MAX_DURATION_MINUTES=30
TWAPX_MAX_MARKET_VOLUME_USD=100000000
TWAPX_MIN_TWAP_SHARE_PERCENT=0.5
```

Это соответствует:

`$300K+ / ≤30 минут / market volume <$100M / TWAP share >0.5%`

## Запуск

```bash
cp .env.example .env
# заполнить TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE

docker compose build
docker compose up -d mysql phpmyadmin
```

Первичная авторизация Telegram user session:

```bash
docker compose run --rm app python -m app.cli login
```

Telethon попросит код из Telegram. Если включена 2FA, попросит пароль. Сессия сохранится в `./sessions`.

Запуск слушателя:

```bash
docker compose up -d app
```

Импорт истории канала, если нужно прогнать старые сообщения:

```bash
docker compose run --rm app python -m app.cli history --limit 5000
```

phpMyAdmin:

```text
http://localhost:8081
```

## Таблицы

- `source_groups` — источники, назначения и фильтры по группам.
- `incoming_messages` — все входящие сообщения из источников.
- `parsed_messages` — результат парсинга каждого сообщения: `accepted`, `rejected`, `skipped`, `error`.
- `twap_signals` — нормализованные TWAP-поля для аналитики и фильтров.

## Добавление новой группы

1. Создать каталог `app/groups/<group_name>/`.
2. Добавить файлы:
   - `config.py`
   - `parser.py`
   - `filters.py`
   - `formatter.py`
   - `processor.py`
3. Подключить процессор в `app/groups/registry.py`.
4. Добавить `<GROUP_NAME>` в `GROUPS` в `.env`.

Так парсинг разных каналов не смешивается.

## Важное по thread_id

Есть два разных thread-id:

- `TWAPX_SOURCE_THREAD_IDS` — какие топики читать из source-чата. Пусто = читать весь source-чат.
- `TWAPX_TARGET_THREAD_ID` — в какой топик отправлять принятое сообщение.

Пример, если источник тоже forum topic:

```env
TWAPX_SOURCE_CHAT_IDS=-1003663170785
TWAPX_SOURCE_THREAD_IDS=4
TWAPX_TARGET_CHAT_ID=-1003918218733
TWAPX_TARGET_THREAD_ID=4
```

Для нескольких source-чатов с разными топиками:

```env
TWAPX_SOURCE_CHAT_IDS=-1001111111111,-1002222222222
TWAPX_SOURCE_CHAT_THREADS=-1001111111111:4;5,-1002222222222:9
```

`TWAPX_TARGET_THREAD_ID=4` передается в Telethon как `reply_to=4`. Для Telegram forum topic это обычно работает как отправка в топик. Если Telegram отправит сообщение не в нужный топик, нужен root message id этого forum topic.

Для входящих сообщений thread определяется через `message.reply_to.reply_to_top_id`, если он есть, иначе через `message.reply_to.reply_to_msg_id`.

## Сборка кода проекта в один файл

Скрипт находится в `tools/dump/main.py` и адаптирован под структуру этого проекта.

Запуск из корня проекта:

```bash
python tools/dump/main.py
```

По умолчанию создаёт рядом со скриптом:

- `tools/dump/project_bundle.txt` — весь код одним файлом;
- `tools/dump/files_list.txt` — список файлов, попавших в дамп.

В дамп входят:

- `app/`
- `tests/`
- `tools/`
- `.env.example`
- `.gitignore`
- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `README.md`

Не входят:

- `.env`
- `sessions/`
- `mysql_data/`
- `__pycache__/`
- `.pytest_cache/`
- результат самого дампа.

Если нужно явно задать корень проекта:

```bash
python tools/dump/main.py --root /path/to/twap_telegram_parser
```

Если нужно включить `.env`, что обычно не рекомендуется:

```bash
python tools/dump/main.py --include-env
```
