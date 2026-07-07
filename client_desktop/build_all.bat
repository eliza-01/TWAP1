@echo off
setlocal
cd /d "%~dp0\.."

echo.
echo === TWAPs desktop clients build: all variants ===
echo Project root: %CD%
echo.

set "TWAPS_NO_PAUSE=1"

call "%~dp0browser\compile_prod.bat"
if errorlevel 1 goto error

call "%~dp0browser\compile_stage.bat"
if errorlevel 1 goto error

call "%~dp0wv2\compile_prod.bat"
if errorlevel 1 goto error

call "%~dp0wv2\compile_stage.bat"
if errorlevel 1 goto error

echo.
echo Done: all desktop clients are in:
echo   dist\browser\prod
echo   dist\browser\stage
echo   dist\wv2\prod
echo   dist\wv2\stage
echo.
pause
exit /b 0

:error
echo.
echo Build failed. Error code: %ERRORLEVEL%
echo.
pause
exit /b 1
