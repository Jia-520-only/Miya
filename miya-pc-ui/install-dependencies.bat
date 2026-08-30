@echo off
cd /d "%~dp0"
echo Installing dependencies (excluding electron)...
call npm install --legacy-peer-deps --ignore-scripts
echo.
echo Installing electron separately...
call npm install --legacy-peer-deps electron --ignore-scripts
echo.
echo Installation complete!
