@echo off
echo Cleaning port 5173...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173') do taskkill /F /PID %%a 2>nul
echo Done.
timeout /t 2
