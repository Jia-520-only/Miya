@echo off
echo ========================================
echo 清理占用端口的进程
echo ========================================

echo.
echo 正在检查端口 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo 发现进程 PID: %%a
    taskkill /F /PID %%a
    echo 已终止进程 %%a
)

echo.
echo 正在检查端口 6379 (Redis)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :6379 ^| findstr LISTENING') do (
    echo 发现进程 PID: %%a
    taskkill /F /PID %%a
    echo 已终止进程 %%a
)

echo.
echo 正在检查端口 7687 (Neo4j)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :7687 ^| findstr LISTENING') do (
    echo 发现进程 PID: %%a
    taskkill /F /PID %%a
    echo 已终止进程 %%a
)

echo.
echo 正在检查端口 5173 (Vite)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    echo 发现进程 PID: %%a
    taskkill /F /PID %%a
    echo 已终止进程 %%a
)

echo.
echo ========================================
echo 清理完成！
echo ========================================
pause
