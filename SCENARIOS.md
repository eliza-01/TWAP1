# Сценарии запуска и перезапуска

Этот файл содержит только практические команды.

Работать из корня проекта:

```powershell
cd C:\Projects\TWAP1
```

## 1. Перезапуск после правок кода

### 1.1. Если менялся основной Telegram-слушатель

docker compose build app
docker compose up -d --force-recreate app

### 1.2. Если менялся локальный клиент

docker compose --profile local build local
docker compose --profile local up -d --force-recreate local

### 1.3. Если менялся Signal Server

docker compose --profile server build signal-server
docker compose --profile server up -d --force-recreate signal-server

### 1.4. Если менялось сразу несколько частей проекта

docker compose --profile local --profile server build
docker compose --profile local --profile server up -d --force-recreate

### 1.5. Если обычная пересборка не помогла используй полную пересборку без Docker-кэша
### это дольше, но надёжнее, если Docker подтягивает старые слои.

docker compose --profile local --profile server build --no-cache
docker compose --profile local --profile server up -d --force-recreate


## 2. Перезапуск без правок кода

Используй этот сценарий, если код не менялся.

Например:

- нужно просто перезапустить приложение;
- завис Telegram-слушатель;
- нужно применить изменения `.env`;
- Docker Desktop перезапускался;
- нужно поднять сервисы после остановки ПК.

### 2.1. Перезапустить только Telegram-слушатель

docker compose restart app

### 2.2. Перезапустить локальный клиент

docker compose --profile local restart local

### 2.3. Перезапустить Signal Server

docker compose --profile server restart signal-server

### 2.4. Перезапустить всё приложение

docker compose --profile local --profile server restart

### 2.5. Полностью остановить и заново поднять всё без удаления данных

docker compose --profile local --profile server down
docker compose --profile local --profile server up -d

Данные сохранятся:

- Telegram-сессия останется в `sessions/`;
- локальные настройки останутся в `local_data/`;
- база данных останется в Docker volume.

## 3. Запуск проекта впервые на ПК

Используй этот сценарий на новом компьютере или после свежего клона проекта.

### 3.2. Создать `.env`

Copy-Item .env.example .env

### Открой `.env` и заполни

### 3.3. Собрать проект
### 3.4. Запустить MySQL и phpMyAdmin
### 3.5. Авторизовать Telegram-пользователя

docker compose build
docker compose up -d mysql phpmyadmin
docker compose run --rm app python -m app.cli login

После команды:

1. Telegram пришлёт код.
2. Введи код в консоль.
3. Если включена 2FA, введи пароль.
4. Сессия сохранится в `sessions/twap_user.session`.

### 3.6. Запустить основной слушатель
### 3.7. Запустить локальный клиент
### 3.8. Запустить Signal Server

docker compose up -d app
docker compose --profile local up -d local
docker compose --profile server up -d signal-server

## 4. Обновление Telegram-сессии

Используй этот сценарий, если нужно:

- авторизовать другого Telegram-пользователя;
- сменить номер Telegram;
- пересоздать сломанную сессию;
- заново пройти логин Telethon.

### 4.1. Остановить Telegram-слушатель
### 4.2. Удалить старую сессию
### 4.4. Заново авторизоваться
### 4.5. Запустить Telegram-слушатель

docker compose stop app
Remove-Item -Force .\sessions\twap_user.session -ErrorAction SilentlyContinue
Remove-Item -Force .\sessions\twap_user.session-journal -ErrorAction SilentlyContinue
docker compose run --rm app python -m app.cli login
docker compose up -d app

## 5. Всё остальное

## 5.1. Создать новую Telegram-сессию, не удаляя старую

Если нужно оставить старую сессию, укажи новый файл сессии.

В `.env`:

```env
TELEGRAM_PHONE=+НОВЫЙ_НОМЕР
TELEGRAM_SESSION_PATH=sessions/twap_user_2.session
```

Потом:

```powershell
docker compose stop app
docker compose run --rm app python -m app.cli login
docker compose up -d app
```

Старая сессия останется здесь:

```text
sessions/twap_user.session
```

Новая сессия будет здесь:

```text
sessions/twap_user_2.session
```

## 5.2. Запустить всё приложение одной командой

```powershell
docker compose --profile local --profile server up -d
```

Поднимутся:

- `app`;
- `mysql`;
- `phpmyadmin`;
- `local`;
- `signal-server`.

## 5.3. Остановить всё приложение без удаления данных

```powershell
docker compose --profile local --profile server down
```

Данные не удаляются.

## 5.4. Остановить всё приложение с удалением базы данных

Внимание: команда удалит MySQL volume и все данные в БД.

```powershell
docker compose --profile local --profile server down -v
```

Не удалятся автоматически:

- `.env`;
- `sessions/`;
- `local_data/`.

## 5.5. Полностью начать с чистой БД, но оставить Telegram-сессию

```powershell
docker compose --profile local --profile server down -v
docker compose up -d mysql phpmyadmin
docker compose up -d app
docker compose --profile local up -d local
docker compose --profile server up -d signal-server
```

## 5.6. Полностью начать с чистой БД и новой Telegram-сессией

```powershell
docker compose --profile local --profile server down -v
Remove-Item -Force .\sessions\twap_user.session -ErrorAction SilentlyContinue
Remove-Item -Force .\sessions\twap_user.session-journal -ErrorAction SilentlyContinue
docker compose up -d mysql phpmyadmin
docker compose run --rm app python -m app.cli login
docker compose up -d app
docker compose --profile local up -d local
docker compose --profile server up -d signal-server
```

## 5.7. Запустить только базу и phpMyAdmin

```powershell
docker compose up -d mysql phpmyadmin
```

## 5.8. Запустить только Telegram-слушатель

```powershell
docker compose up -d app
```

## 5.9. Запустить только локальный клиент

```powershell
docker compose --profile local up -d local
```

## 5.10. Запустить только Signal Server

```powershell
docker compose --profile server up -d signal-server
```

## 5.11. Обновить `.env` и применить настройки

Если менялся только `.env`, код пересобирать не нужно.

Для Telegram-слушателя:

```powershell
docker compose restart app
```

Для локального клиента:

```powershell
docker compose --profile local restart local
```

Для Signal Server:

```powershell
docker compose --profile server restart signal-server
```

Для всего приложения:

```powershell
docker compose --profile local --profile server restart
```
