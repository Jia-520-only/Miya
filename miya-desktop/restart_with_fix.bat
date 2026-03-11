@echo off
echo ========================================
echo Restart Live2D with Local Libraries
echo ========================================

cd /d "%~dp0"

echo.
echo Step 1: Clean port 5173...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 2^>nul') do (
    echo Killing process %%a...
    taskkill /F /PID %%a 2>nul
)
echo Port cleaned.
timeout /t 2

echo.
echo Step 2: Start development server...
echo.
npm run dev

pause
