# Сценарии запуска и перезапуска

Этот файл содержит только практические команды.

Работать из корня проекта:

cd C:\Projects\TWAP1


## 1. Перезапуск после правок кода

Используй этот сценарий, если менялись файлы проекта: `app/`, `tests/`, `Dockerfile`, `requirements.txt`, frontend/local UI, Signal Server и т.д.

### 1.1. Если менялся основной Telegram-слушатель

docker compose build app
docker compose up -d --force-recreate app


### 1.2. Если менялся локальный клиент

docker compose --profile local build local
docker compose --profile local up -d --force-recreate local


### 1.3. Если менялся Signal Server

docker compose --profile server build signal-server
docker compose --profile server up -d --force-recreate signal-server


### 1.4. Если менялось сразу несколько частей проекта !!!!!!!!!!!!!!!

docker compose --profile local --profile server build
docker compose --profile local --profile server up -d --force-recreate


### 1.5. Если обычная пересборка не помогла

Полная пересборка без Docker-кэша. Это дольше, но надёжнее, если Docker подтягивает старые слои.

docker compose --profile local --profile server build --no-cache
docker compose --profile local --profile server up -d --force-recreate


## 2. Перезапуск без правок кода

Используй этот сценарий, если код не менялся.

Важно:

* `restart` подходит только для обычного перезапуска уже созданного контейнера;
* `restart` не применяет изменения `.env`;
* для применения `.env` нужен `up -d --force-recreate`.

### 2.1. Просто перезапустить Telegram-слушатель

docker compose restart app


### 2.2. Просто перезапустить локальный клиент

docker compose --profile local restart local


### 2.3. Просто перезапустить Signal Server

docker compose --profile server restart signal-server


### 2.4. Просто перезапустить всё приложение

docker compose --profile local --profile server restart


### 2.5. Применить изменения `.env`

Если менялся `.env`, код пересобирать не нужно, но контейнеры нужно пересоздать.

Для Telegram-слушателя:

docker compose up -d --force-recreate app


Для локального клиента:

docker compose --profile local up -d --force-recreate local


Для Signal Server:

docker compose --profile server up -d --force-recreate signal-server


Для всего приложения:

docker compose --profile local --profile server up -d --force-recreate


### 2.6. Поднять приложение после остановки ПК или Docker Desktop

docker compose --profile local --profile server up -d


### 2.7. Полностью остановить и заново поднять всё без удаления данных

docker compose --profile local --profile server down
docker compose --profile local --profile server up -d


Данные сохранятся:

* Telegram-сессия останется в `sessions/`;
* локальные настройки останутся в `local_data/`;
* база данных останется в Docker volume.

## 3. Запуск проекта впервые на ПК

Используй этот сценарий на новом компьютере или после свежего клона проекта.

### 3.1. Создать `.env`

Copy-Item .env.example .env


Открой `.env` и заполни нужные значения.

### 3.2. Собрать проект

docker compose --profile local --profile server build


### 3.3. Запустить MySQL и phpMyAdmin

docker compose up -d mysql phpmyadmin


### 3.4. Авторизовать Telegram-пользователя

docker compose run --rm app python -m app.cli login


После команды:

1. Telegram пришлёт код.
2. Введи код в консоль.
3. Если включена 2FA, введи пароль.
4. Сессия сохранится в `sessions/twap_user.session`.

### 3.5. Запустить основной слушатель

docker compose up -d app


### 3.6. Запустить локальный клиент

docker compose --profile local up -d local


### 3.7. Запустить Signal Server

docker compose --profile server up -d signal-server


## 4. Обновление Telegram-сессии

Используй этот сценарий, если нужно:

* авторизовать другого Telegram-пользователя;
* сменить номер Telegram;
* пересоздать сломанную сессию;
* заново пройти логин Telethon.

### 4.1. Остановить Telegram-слушатель

docker compose stop app


### 4.2. Удалить старую сессию

Remove-Item -Force .\sessions\twap_user.session -ErrorAction SilentlyContinue
Remove-Item -Force .\sessions\twap_user.session-journal -ErrorAction SilentlyContinue


### 4.3. Заново авторизоваться

docker compose run --rm app python -m app.cli login


### 4.4. Запустить Telegram-слушатель

docker compose up -d --force-recreate app


## 5. Всё остальное

### 5.1. Создать новую Telegram-сессию, не удаляя старую

Если нужно оставить старую сессию, укажи новый файл сессии.

В `.env`:

env
TELEGRAM_PHONE=+НОВЫЙ_НОМЕР
TELEGRAM_SESSION_PATH=sessions/twap_user_2.session


Потом:

docker compose stop app
docker compose run --rm app python -m app.cli login
docker compose up -d --force-recreate app


Старая сессия останется здесь:

text
sessions/twap_user.session


Новая сессия будет здесь:

text
sessions/twap_user_2.session


### 5.2. Запустить всё приложение одной командой

docker compose --profile local --profile server up -d


Поднимутся:

* `app`;
* `mysql`;
* `phpmyadmin`;
* `local`;
* `signal-server`.

### 5.3. Остановить всё приложение без удаления данных

docker compose --profile local --profile server down


Данные не удаляются.

### 5.4. Остановить всё приложение с удалением базы данных

Внимание: команда удалит MySQL volume и все данные в БД.

docker compose --profile local --profile server down -v


Не удалятся автоматически:

* `.env`;
* `sessions/`;
* `local_data/`.

### 5.5. Полностью начать с чистой БД, но оставить Telegram-сессию

docker compose --profile local --profile server down -v
docker compose up -d mysql phpmyadmin
docker compose up -d app
docker compose --profile local up -d local
docker compose --profile server up -d signal-server


### 5.6. Полностью начать с чистой БД и новой Telegram-сессией

docker compose --profile local --profile server down -v
Remove-Item -Force .\sessions\twap_user.session -ErrorAction SilentlyContinue
Remove-Item -Force .\sessions\twap_user.session-journal -ErrorAction SilentlyContinue
docker compose up -d mysql phpmyadmin
docker compose run --rm app python -m app.cli login
docker compose up -d app
docker compose --profile local up -d local
docker compose --profile server up -d signal-server


### 5.7. Запустить только базу и phpMyAdmin

docker compose up -d mysql phpmyadmin


### 5.8. Запустить только Telegram-слушатель

docker compose up -d app


### 5.9. Запустить только локальный клиент

docker compose --profile local up -d local


### 5.10. Запустить только Signal Server

docker compose --profile server up -d signal-server


### 5.11. Применить `.env` для конкретного сервиса

Для Telegram-слушателя:

docker compose up -d --force-recreate app


Для локального клиента:

docker compose --profile local up -d --force-recreate local


Для Signal Server:

docker compose --profile server up -d --force-recreate signal-server


Для всего приложения:

docker compose --profile local --profile server up -d --force-recreate


### 5.12. Посмотреть логи Telegram-слушателя

docker compose logs -f app


### 5.13. Посмотреть логи локального клиента

docker compose --profile local logs -f local


### 5.14. Посмотреть логи Signal Server

docker compose --profile server logs -f signal-server

