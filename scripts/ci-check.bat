@echo off
REM ========================================
REM  Miya CI/CD 本地检查脚本
REM  模拟 GitHub Actions 的 CI 流程
REM  用法: scripts\ci-check.bat
REM ========================================
setlocal enabledelayedexpansion

echo.
echo  ======================================
echo   Miya CI 本地检查
echo  ======================================
echo.

set PASS=1

REM ---- 1. ruff linting ----
echo [1/4] ruff check ...
ruff check .
if errorlevel 1 (
    echo [FAIL] ruff check 发现问题
    set PASS=0
) else (
    echo [PASS] ruff check
)

REM ---- 2. black formatting check ----
echo.
echo [2/4] black --check ...
black --check core\ hub\ run\
if errorlevel 1 (
    echo [FAIL] black 格式化检查未通过
    set PASS=0
) else (
    echo [PASS] black --check
)

REM ---- 3. bandit security audit ----
echo.
echo [3/4] bandit security audit ...
bandit -r core\ hub\ run\ -ll -f custom 2>&1
if errorlevel 1 (
    echo [FAIL] bandit 发现安全问题
    set PASS=0
) else (
    echo [PASS] bandit
)

REM ---- 4. unit tests ----
echo.
echo [4/4] pytest ...
pytest tests\unit\ -v --tb=short 2>nul
if errorlevel 1 (
    echo [FAIL] 单元测试失败
    set PASS=0
) else (
    echo [PASS] pytest
)

REM ---- summary ----
echo.
echo  ======================================
if "%PASS%"=="1" (
    echo   全部通过！可以 push 了
) else (
    echo   有检查未通过，请修复后重试
)
echo  ======================================
echo.

exit /b %PASS%
