# TWAPs desktop clients

В `client_desktop` теперь разделены две ветки сборки:

```text
client_desktop/
  browser/
    compile_prod.bat
    compile_stage.bat
    browser_client.spec

  wv2/
    compile_prod.bat
    compile_stage.bat
    wv2_client.spec
```

Обе ветки используют общий локальный backend/UI из `app/local` и общий launcher-код из `client_desktop/desktop_common.py`.

## Browser-версия

Открывает локальную панель в браузере.

Prod-сборка для клиентов:

```bat
client_desktop\browser\compile_prod.bat
```

Результат:

```text
dist\browser\prod\TWAPs Browser Client.exe
```

Stage-сборка:

```bat
client_desktop\browser\compile_stage.bat
```

Результат:

```text
dist\browser\stage\TWAPs Browser Client STAGE.exe
```

## WV2-версия

Открывает локальную панель в отдельном окне WebView2/pywebview.

Prod-сборка для клиентов:

```bat
client_desktop\wv2\compile_prod.bat
```

Результат:

```text
dist\wv2\prod\TWAPs.exe
```

Stage-сборка:

```bat
client_desktop\wv2\compile_stage.bat
```

Результат:

```text
dist\wv2\stage\TWAPs STAGE.exe
```

## Endpoints

Compile-скрипты вшивают дефолтный endpoint в exe:

```text
prod  -> https://twaps.ru
stage -> https://beta.twaps.ru
```

Также endpoint можно переопределить без пересборки: положить `.env` рядом с exe.

Prod:

```env
LOCAL_SIGNAL_HTTP_URL=https://twaps.ru
LOCAL_SIGNAL_WS_URL=wss://twaps.ru/ws/signals
```

Stage:

```env
LOCAL_SIGNAL_HTTP_URL=https://beta.twaps.ru
LOCAL_SIGNAL_WS_URL=wss://beta.twaps.ru/ws/signals
```

## Общая сборка

Можно собрать все четыре варианта:

```bat
client_desktop\build_all.bat
```

Старые `build_browser.bat` и `build_wv2.bat` оставлены как совместимые wrapper-скрипты и ведут на stage-сборки.
