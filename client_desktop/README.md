# TWAP Desktop Client

Пользовательский торговый клиент для сборки в `.exe`.

Он запускает локальный интерфейс только на `127.0.0.1`, хранит пользовательские настройки/API-ключи локально и подключается к публичному Signal Server по HTTPS/WebSocket.

По умолчанию stage-сборка использует:

```text
HTTP: https://beta.twaps.ru
WS:   wss://beta.twaps.ru/ws/signals
```

Для prod-сборки перед запуском `build_windows.bat` укажи:

```bat
set TWAP_CLIENT_HTTP_URL=https://twaps.ru
set TWAP_CLIENT_WS_URL=wss://twaps.ru/ws/signals
```

Сборка на Windows:

```bat
client_desktop\build_windows.bat
```

Результат:

```text
dist\TWAP Desktop Client.exe
```

Данные пользователя сохраняются в `%APPDATA%\TWAP Desktop Client`.
