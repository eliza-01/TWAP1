@echo off
setlocal
cd /d "%~dp0"

echo Removing legacy flat desktop build files...
del /F /Q "browser_client.spec" >nul 2>nul
del /F /Q "wv2_client.spec" >nul 2>nul
del /F /Q "build_windows.bat" >nul 2>nul

echo Done.
pause
