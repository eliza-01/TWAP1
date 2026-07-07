# TWAPs desktop clients

В папке две сборки локального клиента. Обе используют текущий FastAPI/UI из `app/local`, не требуют Docker и собираются через PyInstaller.

## 1. Текущая browser-версия

Открывает локальный интерфейс в браузере, как раньше.

```bat
client_desktop\build_browser.bat
```

Результат:

```text
dist\TWAPs Browser Client.exe
```

У этой версии специально оставлена консоль: закрытие консоли останавливает локальный backend. Это fallback/старый вариант.

## 2. Новая WV2-версия

Открывает интерфейс в отдельном окне через pywebview + Microsoft Edge WebView2.

```bat
client_desktop\build_wv2.bat
```

Результат:

```text
dist\TWAPs WV2 Client.exe
```

Особенности WV2-версии:

- не открывает вкладку браузера;
- при закрытии окна останавливает локальный backend;
- если есть открытые сделки, показывает предупреждение перед закрытием;
- не использует Nuitka;
- зависимости open-source: pywebview + PyInstaller. Сам WebView2 Runtime — системный компонент Windows.

## Собрать обе версии

```bat
client_desktop\build_all.bat
```

## WebView2 Runtime

На Windows 11 WebView2 обычно уже установлен. На Windows 10 может отсутствовать. Если WV2-версия не запускается, установи Microsoft Edge WebView2 Runtime или используй browser-версию.

## Где хранятся данные

В собранном `.exe` локальные данные по умолчанию пишутся сюда:

```text
%APPDATA%\TWAPs\
```

Файлы:

```text
settings.json
signals.json
trades.json
```

Для stage/beta или кастомных путей можно положить `.env` рядом с `.exe` или задать переменные окружения:

```env
LOCAL_SIGNAL_HTTP_URL=https://beta.twaps.ru
LOCAL_SIGNAL_WS_URL=wss://beta.twaps.ru/ws/signals
TWAPS_DATA_DIR=C:\TWAPsData
```
