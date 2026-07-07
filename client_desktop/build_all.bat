@echo off
setlocal
cd /d "%~dp0\.."

echo.
echo === TWAPs desktop clients build ===
echo Project root: %CD%
echo.

set "TWAPS_NO_PAUSE=1"

call "%~dp0build_browser.bat"
if errorlevel 1 goto error

call "%~dp0build_wv2.bat"
if errorlevel 1 goto error

echo.
echo Done: both desktop clients are in dist\
echo.
pause
exit /b 0

:error
echo.
echo Build failed. Error code: %ERRORLEVEL%
echo.
pause
exit /b 1
