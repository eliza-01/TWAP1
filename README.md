# TWAP Telegram Parser

Python-сервис для чтения Telegram-каналов через пользовательское Telegram App API (`api_id` / `api_hash`), парсинга TWAP-сообщений, фильтрации, сохранения в MySQL и пересылки принятых сигналов в целевой чат/топик.

## Быстрый старт

Основные команды вынесены в отдельный файл:

```text
SCENARIOS.md
```

Начинай с него. Там собраны самые частые сценарии:

1. перезапуск после правок кода;
2. перезапуск без правок;
3. запуск проекта впервые на ПК;
4. обновление Telegram-сессии;
5. остальные сценарии.

## Состав проекта

Проект запускается через Docker Compose и состоит из нескольких сервисов:

- `app` — основной Telegram-слушатель.
- `mysql` — база данных MySQL 8.4.
- `phpmyadmin` — веб-интерфейс для просмотра БД.
- `local` — локальный торговый клиент с UI.
- `signal-server` — центральный HTTP/WebSocket сервер сигналов.

## Адреса

После запуска адреса зависят от `STAGE` в `.env`.

Prod (`STAGE=OFF`):

```text
Публичный домен:  https://twaps.ru
Локальный клиент: http://localhost:8080
Signal Server:    http://localhost:8090
WebSocket:        ws://localhost:8090/ws/signals
phpMyAdmin:       http://localhost:8081
```

Stage (`STAGE=ON`):

```text
Публичный домен:  https://beta.twaps.ru
Локальный клиент: http://localhost:18080
Signal Server:    http://localhost:18090
WebSocket:        ws://localhost:18090/ws/signals
phpMyAdmin:       http://localhost:18081
```

## Stage / prod запуск

Переключение делается одной переменной в `.env`:

```env
STAGE=ON   # stage, beta.twaps.ru
STAGE=OFF  # prod, twaps.ru
```

Порты задаются парами `PROD_*` и `STAGE_*` в `.env.example`. Скрипт запуска читает `STAGE`, генерирует `.env.runtime` и `.env.compose.generated`, затем запускает Docker Compose с нужными портами.

Windows:

```bat
run.bat --profile server --profile local up -d --build
```

Linux/macOS:

```bash
./run.sh --profile server --profile local up -d --build
```

Или напрямую через Python:

```bash
python tools/compose.py --profile server --profile local up -d --build
```

Если запустить `docker compose up` напрямую без `tools/compose.py`, Docker Compose не сможет сам сделать if/else по `STAGE`, поэтому будут использованы fallback-порты из `docker-compose.yml`.

## Cloudflare Tunnel

Прокидывать наружу нужно только HTTP-сервисы. MySQL наружу через Cloudflare лучше не отдавать.

Prod (`STAGE=OFF`):

```text
twaps.ru      -> http://localhost:8080   # UI
/ws/signals   -> http://localhost:8090   # WebSocket Signal Server
/signals/*    -> http://localhost:8090   # HTTP pending signals
/health       -> http://localhost:8090   # health check
```

Stage (`STAGE=ON`):

```text
beta.twaps.ru -> http://localhost:18080  # UI
/ws/signals   -> http://localhost:18090  # WebSocket Signal Server
/signals/*    -> http://localhost:18090  # HTTP pending signals
/health       -> http://localhost:18090  # health check
```

phpMyAdmin лучше не публиковать. Если всё же нужно временно открыть — prod `8081`, stage `18081`, желательно закрыть Cloudflare Access.


## Основные файлы и папки

```text
.env                         локальные настройки проекта
.env.example                 пример настроек
sessions/                    Telegram user session
sessions/twap_user.session   файл авторизации Telegram
local_data/                  локальные настройки клиента
mysql_data                   Docker volume с базой данных
```

Важно:

- `.env` не коммитится.
- `sessions/*.session` не коммитятся.
- `local_data/` не коммитится.
- База данных хранится в Docker volume `mysql_data`.

## Первичная настройка `.env`

Если файла `.env` ещё нет, создай его из `.env.example`.

В `.env` нужно заполнить Telegram App данные. Активный набор выбирается переменной `STAGE`:

```env
STAGE=OFF

PROD_TELEGRAM_API_ID=12345678
PROD_TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
PROD_TELEGRAM_PHONE=+79990000000

STAGE_TELEGRAM_API_ID=87654321
STAGE_TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
STAGE_TELEGRAM_PHONE=+79990000000
```

`TELEGRAM_API_ID` и `TELEGRAM_API_HASH` берутся здесь:

```text
https://my.telegram.org/apps
```

`TELEGRAM_SESSION_PATH` по умолчанию общий:

```env
TELEGRAM_SESSION_PATH=sessions/twap_user.session
```

Если нужны разные session-файлы для prod и stage, можно указать:

```env
PROD_TELEGRAM_SESSION_PATH=sessions/twap_prod_user.session
STAGE_TELEGRAM_SESSION_PATH=sessions/twap_stage_user.session
```

## Настройки TWAPx

Источник и назначение теперь задаются одной строкой в формате `chat_id[:thread_id]`. Активный набор выбирается переменной `STAGE`:

```env
PROD_TWAPX_SOURCES=-1003663170785
PROD_TWAPX_TARGET=-1003918218733:4
PROD_TWAPX_ENABLED=true

STAGE_TWAPX_SOURCES=-1003918218733:2
STAGE_TWAPX_TARGET=-1003918218733:4
STAGE_TWAPX_ENABLED=true
```

Если у source-чата нет forum topic/thread, указывай только chat id без `:`. Пример смешанного списка:

```env
STAGE_TWAPX_SOURCES=-1003918218733:2,-1003918218734:3,-1003918218735,-1003918218736,-1003918218737:1
```

Для target тоже используется один формат:

```env
TWAPX_TARGET=-1003918218733:4  # отправлять в topic/thread 4
TWAPX_TARGET=-1003918218733    # отправлять просто в чат без topic/thread
```

Старые переменные `TWAPX_SOURCE_CHAT_IDS`, `TWAPX_SOURCE_THREAD_IDS`, `TWAPX_SOURCE_CHAT_THREADS`, `TWAPX_TARGET_CHAT_ID`, `TWAPX_TARGET_THREAD_ID` оставлены только для обратной совместимости.

Фильтры по умолчанию:

```env
TWAPX_MIN_USD=300000
TWAPX_MAX_DURATION_MINUTES=30
TWAPX_MAX_MARKET_VOLUME_USD=100000000
TWAPX_MIN_TWAP_SHARE_PERCENT=0.5
```

Это означает:

```text
TWAP объём >= $300K
Время исполнения <= 30 минут
Market volume < $100M
TWAP share > 0.5%
```

## Debug thread

Debug thread получает отчёты по обработке сообщений:

- `accepted`
- `rejected`
- `error`

Настройки:

```env
DEBUG_ENABLED=true
DEBUG_CHAT_ID=-1003918218733
DEBUG_THREAD_ID=48
DEBUG_SEND_SKIPPED=false
```

`DEBUG_SEND_SKIPPED=false` лучше оставить по умолчанию, чтобы не засорять топик неподдержанными сообщениями.

Правило reply:

- если исходное сообщение находится в том же чате и том же debug-топике, debug-отчёт отправляется reply на исходное сообщение;
- если исходное сообщение в другом чате или другом топике, отчёт отправляется в `DEBUG_THREAD_ID` reply на root-сообщение debug-топика, а внутри отчёта указывается `Source chat/thread/msg`.

Это ограничение Telegram: нельзя одновременно отправить сообщение в один topic и сделать его reply на сообщение из другого topic.

## Локальный клиент

Локальный клиент запускает MVP-интерфейс для пользователя.

В нём можно:

- выбрать биржу;
- включить или выключить биржу;
- сохранить локальный Binance API key и Secret key;
- проверить подключение;
- посмотреть баланс;
- посмотреть список futures-активов;
- посмотреть позиции;
- вручную открыть или закрыть market-сделку.
- всегда слушать Signal Server через WebSocket и показывать состояние соединения.

Локальные настройки сохраняются здесь:

```text
local_data/settings.json
local_data/signals.json
local_data/trades.json
```

Эти файлы остаются локально у каждого пользователя.

## Signal Server

Signal Server читает принятые `twap_created` сигналы из MySQL и отдаёт их локальным клиентам.

Доступные адреса:

```text
HTTP:      http://localhost:8090
WebSocket: ws://localhost:8090/ws/signals
Health:    http://localhost:8090/health
```

Локальный клиент сам держит исходящее WebSocket-соединение с сервером и слушает сигналы всегда. Это важно: серверу не нужно пробивать NAT/firewall пользователя входящими запросами.

Адреса Signal Server задаются через `.env`: `LOCAL_SIGNAL_WS_URL` и `LOCAL_SIGNAL_HTTP_URL`. В UI ручной ввод адресов и синхронизация убраны.

Защита Signal Server задаётся только через `.env` и не показывается в UI:

```env
SIGNAL_SERVER_ACCESS_KEY=сложный_ключ
LOCAL_SIGNAL_ACCESS_KEY=тот_же_сложный_ключ
SIGNAL_SERVER_DB_CHECK_SECONDS=0.5
SIGNAL_SERVER_MAX_WS_CLIENTS=120
SIGNAL_SERVER_HTTP_MAX_PER_MINUTE=300
SIGNAL_SERVER_HEALTH_MIN_INTERVAL_SECONDS=2
SIGNAL_SERVER_PENDING_MIN_INTERVAL_SECONDS=5
SIGNAL_SERVER_WS_MIN_CONNECT_INTERVAL_SECONDS=1
```

Если `SIGNAL_SERVER_ACCESS_KEY` пустой, HTTP/WebSocket остаются без авторизации. Для публичного сервера ключ обязателен.

Если WebSocket-соединение оборвалось, клиент хранит `last_signal_id` и при переподключении получает пропущенные сигналы через WebSocket hello. Повторные подключения идут с backoff, чтобы клиенты не долбили сервер при аварии.

## Таблицы в базе данных

Основные таблицы:

- `source_groups` — источники, назначения и фильтры по группам.
- `incoming_messages` — все входящие сообщения из источников.
- `parsed_messages` — результат парсинга каждого сообщения: `accepted`, `rejected`, `skipped`, `error`.
- `twap_signals` — нормализованные TWAP-поля для аналитики и фильтров.

Данные для подключения к MySQL берутся из `.env`:

```env
MYSQL_DATABASE=twap_parser
MYSQL_USER=twap_user
MYSQL_PASSWORD=twap_password
MYSQL_ROOT_PASSWORD=root_password
```

## Реакция на завершение или отмену TWAP

Сообщения вида:

```text
✅ TWAP завершён
❌ TWAP отменён
```

тоже парсятся и сохраняются.

Логика:

1. raw-сообщение сохраняется в `incoming_messages`;
2. результат парсинга сохраняется в `parsed_messages`;
3. нормализованные поля закрытия сохраняются в `twap_signals`;
4. если сообщение закрытия или отмены является reply на исходный сигнал, который ранее прошёл фильтр и был отправлен в target, сервис отправляет уведомление о выходе в target;
5. уведомление о выходе отправляется reply на ранее пересланный сигнал;
6. если id пересланного сообщения не найден, отправка идёт в `TWAPX_TARGET_THREAD_ID`.

Если исходный сигнал не проходил фильтр, закрытие или отмена только сохраняется в БД и не пересылается.

Для связи используется `reply_to_message_id` исходного Telegram-сообщения.

## Важное по thread_id

В `.env` больше не нужно разделять chat id и thread id на разные переменные. Используется формат:

```env
TWAPX_SOURCES=-1001111111111:4,-1002222222222:9,-1003333333333
TWAPX_TARGET=-1003918218733:4
```

Правила:

- `chat_id:thread_id` — слушать или отправлять в конкретный forum topic/thread;
- `chat_id` без `:` — слушать весь чат или отправлять просто в чат;
- несколько source-чатов разделяются запятой;
- для нескольких топиков одного чата можно повторить chat id: `-1001:4,-1001:5`.

`thread_id` для target передаётся в Telethon как `reply_to=<thread_id>`. Для Telegram forum topic это обычно работает как отправка в топик. Если Telegram отправит сообщение не в нужный топик, нужен root message id этого forum topic.

Для входящих сообщений thread определяется так:

1. `message.reply_to.reply_to_top_id`, если он есть;
2. иначе `message.reply_to.reply_to_msg_id`;
3. иначе `message.reply_to_msg_id`.

## Добавление новой группы

Для новой группы парсинга:

1. Создать каталог:

```text
app/groups/<group_name>/
```

2. Добавить файлы:

```text
config.py
parser.py
filters.py
formatter.py
processor.py
```

3. Подключить процессор в:

```text
app/groups/registry.py
```

4. Добавить имя группы в `.env`:

```env
GROUPS=twapx,new_group
```

Так парсинг разных каналов не смешивается.

## Разделение ответственности

Структура проекта:

```text
app/exchanges/core/              общий контракт бирж
app/exchanges/binance/              изолированный Binance USDⓈ-M Futures REST-адаптер
app/local/                       локальный UI, настройки, клиент сигналов
app/local/api/routes/            API локального UI
app/signal_server/               центральный HTTP/WebSocket сервер сигналов
app/signal_server/api/routes/    API сервера сигналов
app/groups/twapx/                логика TWAPx-группы
app/db/                          подключение, миграции, репозитории БД
app/telegram/                    Telegram runtime
```

Для добавления новой биржи нужно создать новый каталог:

```text
app/exchanges/<exchange>/
```

И зарегистрировать адаптер в:

```text
app/exchanges/registry.py
```

