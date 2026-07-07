@echo off
setlocal
cd /d "%~dp0\.."

echo.
echo === TWAPs WV2 Client build ===
echo Project root: %CD%
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

"%VENV_PY%" -m pip install -r requirements.txt -r client_desktop\requirements-browser.txt -r client_desktop\requirements-wv2.txt
if errorlevel 1 goto error

echo.
echo Building WV2 client...
"%VENV_PY%" -m PyInstaller --noconfirm --clean client_desktop\wv2_client.spec
if errorlevel 1 goto error

echo.
echo Done: dist\TWAPs WV2 Client.exe
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

:error
echo.
echo Build failed. Error code: %ERRORLEVEL%
echo.
if not "%TWAPS_NO_PAUSE%"=="1" pause
exit /b 1
