@echo off
setlocal
cd /d "%~dp0"

python -m pip install --progress-bar on bandit pytest-timeout

echo.
echo ==============================================
echo [1/6] 语法预检 (compileall)
echo ==============================================
python -m compileall -q memory core hub run || goto :fail

echo.
echo ==============================================
echo [2/6] ruff check
echo ==============================================
python -m ruff check . || goto :fail

echo.
echo ==============================================
echo [3/6] ruff format
echo ==============================================
python -m ruff format . || goto :fail
python -m ruff format --check . || goto :fail

echo.
echo ==============================================
echo [4/6] bandit 安全扫描
echo ==============================================
python -m bandit -c .bandit -r core hub run -ll || goto :fail

echo.
echo ==============================================
echo [5/6] faiss AVX2 检测
echo ==============================================
python setup/scripts/check_faiss_avx2.py
if errorlevel 1 echo [WARN] faiss 未安装或无 AVX2 扩展，仅影响检索速度，不影响验证

echo.
echo ==============================================
echo [6/6] pytest 单元测试
echo ==============================================
python -m pytest tests/unit/test_config_loader_fixes.py -v || goto :fail
python -m pytest tests/ -v --tb=short --timeout=60 --capture=no || goto :fail

echo.
echo ==============================================
echo [OK] 全部验证通过
echo ==============================================
pause
exit /b 0

:fail
echo.
echo ==============================================
echo [FAIL] 验证失败，已提前停止（修正后重新运行）
echo ==============================================
pause
exit /b 1
