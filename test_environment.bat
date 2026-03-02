@echo off
chcp 65001 >nul
echo ========================================
echo   MIYA Environment Test
echo ========================================
echo.

echo [1/5] Checking Python...
python --version
if %errorlevel% neq 0 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)
echo [OK] Python is available
echo.

echo [2/5] Checking Virtual Environment...
if not exist venv (
    echo [ERROR] Virtual environment not found
    pause
    exit /b 1
)
echo [OK] Virtual environment exists
echo.

echo [3/5] Activating Virtual Environment...
call venv\Scripts\activate.bat
echo [OK] Virtual environment activated
echo.

echo [4/5] Checking Core Packages...
echo - fastapi...
python -c "import fastapi; print('  Version:', fastapi.__version__)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] fastapi not installed
) else (
    echo [OK] fastapi is installed
)

echo - uvicorn...
python -c "import uvicorn; print('  Version:', uvicorn.__version__)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] uvicorn not installed
) else (
    echo [OK] uvicorn is installed
)

echo - redis...
python -c "import redis; print('  Version:', redis.__version__)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] redis not installed
) else (
    echo [OK] redis is installed
)

echo - neo4j...
python -c "import neo4j; print('  Version:', neo4j.__version__)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] neo4j not installed
) else (
    echo [OK] neo4j is installed
)

echo - chromadb...
python -c "import chromadb; print('  Version:', chromadb.__version__)" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] chromadb not installed
) else (
    echo [OK] chromadb is installed
)
echo.

echo [5/5] Checking Configuration...
if not exist config\.env (
    echo [WARNING] config\.env not found
    echo          Please copy config\.env.example to config\.env
) else (
    echo [OK] Configuration file exists
)
echo.

echo ========================================
echo   Test Complete
echo ========================================
echo.
echo Next steps:
echo 1. Edit config\.env with your settings
echo 2. Run start.bat to launch MIYA
echo.
pause
