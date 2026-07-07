@echo off
setlocal EnableExtensions

set "TWAP_KIND=%~1"
set "TWAP_ENV=%~2"

if "%TWAP_KIND%"=="" goto usage
if "%TWAP_ENV%"=="" goto usage

cd /d "%~dp0\.."

if /I "%TWAP_KIND%"=="browser" (
  set "TWAP_SPEC=client_desktop\browser\browser_client.spec"
  set "TWAP_REQS=-r requirements.txt -r client_desktop\requirements-browser.txt"
  set "TWAP_KIND_TITLE=Browser"
) else if /I "%TWAP_KIND%"=="wv2" (
  set "TWAP_SPEC=client_desktop\wv2\wv2_client.spec"
  set "TWAP_REQS=-r requirements.txt -r client_desktop\requirements-browser.txt -r client_desktop\requirements-wv2.txt"
  set "TWAP_KIND_TITLE=WV2"
) else (
  echo Unknown client kind: %TWAP_KIND%
  goto error
)

if /I "%TWAP_ENV%"=="prod" (
  set "TWAP_BUILD_FLAVOR=prod"
  set "TWAP_CLIENT_HTTP_URL=https://twaps.ru"
  set "TWAP_CLIENT_WS_URL=wss://twaps.ru/ws/signals"
  set "TWAP_APP_TITLE=TWAPs"
  if /I "%TWAP_KIND%"=="wv2" (
    set "TWAP_EXE_NAME=TWAPs"
  ) else (
    set "TWAP_EXE_NAME=TWAPs Browser Client"
  )
) else if /I "%TWAP_ENV%"=="stage" (
  set "TWAP_BUILD_FLAVOR=stage"
  set "TWAP_CLIENT_HTTP_URL=https://beta.twaps.ru"
  set "TWAP_CLIENT_WS_URL=wss://beta.twaps.ru/ws/signals"
  set "TWAP_APP_TITLE=TWAPs STAGE"
  if /I "%TWAP_KIND%"=="wv2" (
    set "TWAP_EXE_NAME=TWAPs STAGE"
  ) else (
    set "TWAP_EXE_NAME=TWAPs Browser Client STAGE"
  )
) else (
  echo Unknown build env: %TWAP_ENV%
  goto error
)

set "TWAP_DIST=dist\%TWAP_KIND%\%TWAP_BUILD_FLAVOR%"

echo.
echo === TWAPs %TWAP_KIND_TITLE% %TWAP_BUILD_FLAVOR% build ===
echo Project root: %CD%
echo Endpoint HTTP: %TWAP_CLIENT_HTTP_URL%
echo Endpoint WS:   %TWAP_CLIENT_WS_URL%
echo Output:        %TWAP_DIST%\%TWAP_EXE_NAME%.exe
echo.

call :find_python
if errorlevel 1 goto python_missing

echo Using Python command: %TWAPS_PY%
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %TWAPS_PY% -m venv .venv
  if errorlevel 1 goto error
)

set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo Virtual environment was not created correctly: %VENV_PY%
  goto error
)

echo Installing dependencies...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto error

"%VENV_PY%" -m pip install %TWAP_REQS%
if errorlevel 1 goto error

echo Writing generated build config...
"%VENV_PY%" -c "from pathlib import Path; p=Path('client_desktop/build_config_generated.py'); p.write_text('BUILD_FLAVOR = '+repr('%TWAP_BUILD_FLAVOR%')+'\nDEFAULT_HTTP_URL = '+repr('%TWAP_CLIENT_HTTP_URL%')+'\nDEFAULT_WS_URL = '+repr('%TWAP_CLIENT_WS_URL%')+'\nAPP_TITLE = '+repr('%TWAP_APP_TITLE%')+'\n', encoding='utf-8')"
if errorlevel 1 goto error

echo.
echo Building %TWAP_KIND_TITLE% %TWAP_BUILD_FLAVOR% client...
if exist "%TWAP_DIST%\%TWAP_EXE_NAME%.exe" (
  taskkill /F /IM "%TWAP_EXE_NAME%.exe" >nul 2>nul
  del /F /Q "%TWAP_DIST%\%TWAP_EXE_NAME%.exe" >nul 2>nul
)

"%VENV_PY%" -m PyInstaller --noconfirm --clean --distpath "%TWAP_DIST%" --workpath "build\%TWAP_KIND%_%TWAP_BUILD_FLAVOR%" "%TWAP_SPEC%"
if errorlevel 1 goto error

echo.
echo Done: %TWAP_DIST%\%TWAP_EXE_NAME%.exe
echo.
if not "%TWAPS_NO_PAUSE%"=="1" pause
exit /b 0

:find_python
set "TWAPS_PY="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 --version >nul 2>nul
  if not errorlevel 1 (
    set "TWAPS_PY=py -3.12"
    exit /b 0
  )
  py -3 --version >nul 2>nul
  if not errorlevel 1 (
    set "TWAPS_PY=py -3"
    exit /b 0
  )
)
python --version >nul 2>nul
if not errorlevel 1 (
  set "TWAPS_PY=python"
  exit /b 0
)
python3 --version >nul 2>nul
if not errorlevel 1 (
  set "TWAPS_PY=python3"
  exit /b 0
)
exit /b 1

:python_missing
echo Python 3 was not found.
echo.
echo Install Python 3.12 x64 and rerun this script.
echo Recommended command:
echo   winget install -e --id Python.Python.3.12
echo.
echo Or install it from python.org and enable "Add python.exe to PATH".
echo.
if not "%TWAPS_NO_PAUSE%"=="1" pause
exit /b 1

:usage
echo Usage: client_desktop\_compile_client.bat browser^|wv2 prod^|stage
goto error

:error
echo.
echo Build failed. Error code: %ERRORLEVEL%
echo.
if not "%TWAPS_NO_PAUSE%"=="1" pause
exit /b 1
