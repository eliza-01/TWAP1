# Сценарии запуска и перезапуска

Этот файл содержит только практические команды для текущей схемы `stage/prod`.

Работать из корня проекта:

```powershell
cd C:\Projects\TWAP1
```

Важно: после разделения `stage/prod` **не используй обычный `docker compose ...` для запуска проекта**. Запускай через `run.bat`, потому что он читает `STAGE` из `.env`, генерирует `.env.compose.generated` и только потом запускает Docker Compose с правильными портами и именем проекта.

```powershell
run.bat ...
```

Альтернатива без bat:

```powershell
python tools\compose.py ...
```

## 0. Как выбрать prod или stage

В `.env`:

```env
STAGE=OFF
```

Это prod:

```text
twaps.ru
UI:            8080
Signal Server: 8090
phpMyAdmin:    8081
MySQL host:    3306
Compose name:  twap_prod
```

В `.env`:

```env
STAGE=ON
```

Это stage:

```text
beta.twaps.ru
UI:            18080
Signal Server: 18090
phpMyAdmin:    18081
MySQL host:    13306
Compose name:  twap_stage
```

После выбора окружения заполни соответствующие переменные:

```env
PROD_TELEGRAM_API_ID=
PROD_TELEGRAM_API_HASH=
PROD_TELEGRAM_PHONE=
PROD_TWAPX_SOURCES=-1003663170785
PROD_TWAPX_TARGET=-1003918218733:4
PROD_TWAPX_ENABLED=true

STAGE_TELEGRAM_API_ID=
STAGE_TELEGRAM_API_HASH=
STAGE_TELEGRAM_PHONE=
STAGE_TWAPX_SOURCES=-1003918218733:2
STAGE_TWAPX_TARGET=-1003918218733:4
STAGE_TWAPX_ENABLED=true
```

Формат `TWAPX_SOURCES`: `chat_id[:thread_id],chat_id[:thread_id]`. Если thread/topic нет — указывай только `chat_id` без `:`.

`TELEGRAM_SESSION_PATH=sessions/twap_user.session` можно оставить единым для обоих окружений. Если нужны разные session-файлы, заполни `PROD_TELEGRAM_SESSION_PATH` и `STAGE_TELEGRAM_SESSION_PATH`.

## 1. Главная команда: полный перезапуск после правок кода

Используй этот сценарий, если менялись файлы проекта: `app/`, `Dockerfile`, `requirements.txt`, local UI, Signal Server, логика бирж, fallback, парсеры и т.д.

### 1.1. Полностью пересобрать и перезапустить всё приложение

```powershell
run.bat --profile local --profile server down
run.bat --profile local --profile server up -d --build --force-recreate
```

Данные не удаляются:

* база MySQL остаётся в Docker volume;
* Telegram-сессия остаётся в `sessions/`;
* локальные настройки остаются в `local_data/`.

После запуска должны быть контейнеры:

```text
twap_prod_mysql / twap_stage_mysql
twap_prod_phpmyadmin / twap_stage_phpmyadmin
twap_prod_parser_app / twap_stage_parser_app
twap_prod_local_client / twap_stage_local_client
twap_prod_signal_server / twap_stage_signal_server
```

### 1.2. Если обычная пересборка не помогла

Полная пересборка без Docker-кэша. Это дольше, но надёжнее, если Docker подтягивает старые слои.

```powershell
run.bat --profile local --profile server down
run.bat --profile local --profile server build --no-cache
run.bat --profile local --profile server up -d --force-recreate
```

## 2. Перезапуск без правок кода

Используй этот сценарий, если код не менялся.

### 2.1. Просто перезапустить всё приложение

```powershell
run.bat --profile local --profile server restart
```

### 2.2. Поднять приложение после остановки ПК или Docker Desktop

```powershell
run.bat --profile local --profile server up -d
```

### 2.3. Полностью остановить и заново поднять всё без удаления данных

```powershell
run.bat --profile local --profile server down
run.bat --profile local --profile server up -d
```

## 3. Применить изменения `.env`

Важно:

* `restart` не применяет изменения `.env`;
* для применения `.env` нужен `up -d --force-recreate`;
* `run.bat` каждый раз заново генерирует `.env.compose.generated` из текущего `.env`.

### 3.1. Применить `.env` для всего приложения

```powershell
run.bat --profile local --profile server up -d --force-recreate
```

### 3.2. Применить `.env` после смены `STAGE=ON/OFF`

На разных машинах просто выставь нужное значение в `.env` и запусти:

```powershell
run.bat --profile local --profile server up -d --build --force-recreate
```

Если переключаешь `STAGE` на одной и той же машине и хочешь остановить старое окружение:

```powershell
run.bat --profile local --profile server down
```

Потом поменяй `STAGE` в `.env` и подними новое окружение:

```powershell
run.bat --profile local --profile server up -d --build --force-recreate
```

## 4. Перезапуск отдельных частей после правок

### 4.1. Если менялся основной Telegram-слушатель

```powershell
run.bat build app
run.bat up -d --force-recreate app
```

### 4.2. Если менялся локальный клиент

```powershell
run.bat --profile local build local
run.bat --profile local up -d --force-recreate local
```

### 4.3. Если менялся Signal Server

```powershell
run.bat --profile server build signal-server
run.bat --profile server up -d --force-recreate signal-server
```

### 4.4. Если менялось сразу несколько частей проекта

```powershell
run.bat --profile local --profile server up -d --build --force-recreate
```

## 5. Запуск проекта впервые на ПК

Используй этот сценарий на новом компьютере или после свежего клона проекта.

### 5.1. Создать `.env`

```powershell
Copy-Item .env.example .env
```

Открой `.env` и заполни нужные значения.

Для prod:

```env
STAGE=OFF
```

Для stage:

```env
STAGE=ON
```

### 5.2. Собрать проект

```powershell
run.bat --profile local --profile server build
```

### 5.3. Запустить MySQL и phpMyAdmin

```powershell
run.bat up -d mysql phpmyadmin
```

### 5.4. Авторизовать Telegram-пользователя

```powershell
run.bat run --rm app python -m app.cli login
```

После команды:

1. Telegram пришлёт код.
2. Введи код в консоль.
3. Если включена 2FA, введи пароль.
4. Сессия сохранится в `TELEGRAM_SESSION_PATH`, либо в `PROD_TELEGRAM_SESSION_PATH` / `STAGE_TELEGRAM_SESSION_PATH`, если они заданы.

### 5.5. Запустить всё приложение

```powershell
run.bat --profile local --profile server up -d
```

Поднимутся:

* `app`;
* `mysql`;
* `phpmyadmin`;
* `local`;
* `signal-server`.

## 6. Обновление Telegram-сессии

Используй этот сценарий, если нужно:

* авторизовать другого Telegram-пользователя;
* сменить номер Telegram;
* пересоздать сломанную сессию;
* заново пройти логин Telethon.

### 6.1. Остановить Telegram-слушатель

```powershell
run.bat stop app
```

### 6.2. Удалить старую сессию

```powershell
Remove-Item -Force .\sessions\twap_user.session -ErrorAction SilentlyContinue
Remove-Item -Force .\sessions\twap_user.session-journal -ErrorAction SilentlyContinue
Remove-Item -Force .\sessions\twap_prod_user.session -ErrorAction SilentlyContinue
Remove-Item -Force .\sessions\twap_prod_user.session-journal -ErrorAction SilentlyContinue
Remove-Item -Force .\sessions\twap_stage_user.session -ErrorAction SilentlyContinue
Remove-Item -Force .\sessions\twap_stage_user.session-journal -ErrorAction SilentlyContinue
```

### 6.3. Заново авторизоваться

```powershell
run.bat run --rm app python -m app.cli login
```

### 6.4. Запустить Telegram-слушатель

```powershell
run.bat up -d --force-recreate app
```

## 7. Остановить приложение

### 7.1. Остановить всё приложение без удаления данных

```powershell
run.bat --profile local --profile server down
```

Данные не удаляются.

### 7.2. Остановить всё приложение с удалением базы данных

Внимание: команда удалит MySQL volume и все данные в БД.

```powershell
run.bat --profile local --profile server down -v
```

Не удалятся автоматически:

* `.env`;
* `sessions/`;
* `local_data/`.

## 8. Запуск отдельных сервисов

### 8.1. Запустить только базу и phpMyAdmin

```powershell
run.bat up -d mysql phpmyadmin
```

### 8.2. Запустить только Telegram-слушатель

```powershell
run.bat up -d app
```

### 8.3. Запустить только локальный клиент

```powershell
run.bat --profile local up -d local
```

### 8.4. Запустить только Signal Server

```powershell
run.bat --profile server up -d signal-server
```

## 9. Логи

### 9.1. Посмотреть логи Telegram-слушателя

```powershell
run.bat logs -f app
```

### 9.2. Посмотреть логи локального клиента

```powershell
run.bat --profile local logs -f local
```

### 9.3. Посмотреть логи Signal Server

```powershell
run.bat --profile server logs -f signal-server
```

### 9.4. Посмотреть логи всего приложения

```powershell
run.bat --profile local --profile server logs -f
```

## 10. Проверить контейнеры и порты

### 10.1. Список контейнеров текущего окружения

```powershell
run.bat --profile local --profile server ps
```

### 10.2. Проверить сгенерированные порты

```powershell
Get-Content .env.compose.generated
```

Ищи строки:

```env
APP_ENV=prod
PUBLIC_DOMAIN=twaps.ru
LOCAL_UI_PORT=8080
SIGNAL_SERVER_PORT=8090
PHPMYADMIN_PORT=8081
MYSQL_HOST_PORT=3306
TELEGRAM_SESSION_PATH=sessions/twap_user.session
TWAPX_SOURCES=...
TWAPX_TARGET=...
```

или:

```env
APP_ENV=stage
PUBLIC_DOMAIN=beta.twaps.ru
LOCAL_UI_PORT=18080
SIGNAL_SERVER_PORT=18090
PHPMYADMIN_PORT=18081
MYSQL_HOST_PORT=13306
TELEGRAM_SESSION_PATH=sessions/twap_user.session
TWAPX_SOURCES=...
TWAPX_TARGET=...
```

## 11. Если мешают старые контейнеры `twap1`

Если раньше проект запускался старым способом и в Docker Desktop осталась группа `twap1`, она может занимать порты `8080`, `8090`, `8081`, `3306`.

Остановить старый проект:

```powershell
docker compose -p twap1 down
```

Потом поднять текущий проект:

```powershell
run.bat --profile local --profile server up -d --build --force-recreate
```

## 12. Cloudflare ports

Prod, если `STAGE=OFF`:

```text
twaps.ru             -> http://localhost:8080
/twap UI             -> localhost:8080
/ws/signals          -> http://localhost:8090
/health              -> http://localhost:8090
/signals             -> http://localhost:8090
```

Stage, если `STAGE=ON`:

```text
beta.twaps.ru        -> http://localhost:18080
/twap UI             -> localhost:18080
/ws/signals          -> http://localhost:18090
/health              -> http://localhost:18090
/signals             -> http://localhost:18090
```

`phpMyAdmin` наружу лучше не публиковать. Если временно нужно, используй Cloudflare Access:

```text
prod:  localhost:8081
stage: localhost:18081
```
