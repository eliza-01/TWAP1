@echo off
setlocal
cd /d "%~dp0\.."

REM Stage defaults. For prod build override before running:
REM set TWAP_CLIENT_HTTP_URL=https://twaps.ru
REM set TWAP_CLIENT_WS_URL=wss://twaps.ru/ws/signals
set TWAP_CLIENT_HTTP_URL=https://beta.twaps.ru
set TWAP_CLIENT_WS_URL=wss://beta.twaps.ru/ws/signals

python -m pip install -r client_desktop\requirements-client.txt
python -m PyInstaller ^
  --name "TWAP Desktop Client" ^
  --onefile ^
  --clean ^
  --add-data "app;app" ^
  client_desktop\twap_desktop_client.py

echo.
echo Build finished: dist\TWAP Desktop Client.exe
endlocal
