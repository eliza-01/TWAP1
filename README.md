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


## Debug thread

Debug thread получает отчет по каждому обработанному сообщению: `accepted`, `rejected`, `error`.
`skipped` по умолчанию не отправляется, чтобы не шуметь служебными и неподдержанными сообщениями.

```env
DEBUG_ENABLED=true
DEBUG_CHAT_ID=-1003918218733
DEBUG_THREAD_ID=48
DEBUG_SEND_SKIPPED=false
```

Правило reply:

- если исходное сообщение находится в том же чате и том же debug-топике, debug-отчет отправляется reply на исходное сообщение;
- если исходное сообщение в другом чате или другом топике, отчет отправляется в `DEBUG_THREAD_ID` reply на root-сообщение debug-топика, а внутри отчета указывается `Source chat/thread/msg`.

Это ограничение Telegram: нельзя одновременно отправить сообщение в один topic и сделать его reply на сообщение из другого topic.

## Таблицы

- `source_groups` — источники, назначения и фильтры по группам.
- `incoming_messages` — все входящие сообщения из источников.
- `parsed_messages` — результат парсинга каждого сообщения: `accepted`, `rejected`, `skipped`, `error`.
- `twap_signals` — нормализованные TWAP-поля для аналитики и фильтров.


## Реакция на завершение / отмену TWAP

Сообщения вида `✅ TWAP завершён` и `❌ TWAP отменён` тоже парсятся и сохраняются.

Логика:

1. raw-сообщение сохраняется в `incoming_messages`;
2. результат парсинга сохраняется в `parsed_messages`;
3. нормализованные поля закрытия сохраняются в `twap_signals`;
4. если сообщение закрытия/отмены является reply на исходный сигнал, который ранее прошёл фильтр и был отправлен в target, сервис отправляет уведомление о выходе в target;
5. уведомление о выходе отправляется reply на ранее пересланный сигнал. Если id пересланного сообщения не найден, отправка идёт в `TWAPX_TARGET_THREAD_ID`.

Если исходный сигнал не проходил фильтр, закрытие/отмена только сохраняется в БД и не пересылается.

Для связи используется `reply_to_message_id` исходного Telegram-сообщения.

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
