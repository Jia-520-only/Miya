@echo off
REM ============================================
REM Milvus 数据库启动脚本
REM ============================================

echo [1/3] 启动 Milvus 相关服务...
docker-compose -f docker-compose.milvus.yml up -d

if %errorlevel% neq 0 (
    echo [ERROR] Milvus 启动失败
    pause
    exit /b 1
)

echo [OK] Milvus 服务已启动
echo.
echo 服务列表:
docker-compose -f docker-compose.milvus.yml ps
echo.

echo [2/3] 等待服务就绪...
timeout /t 15 /nobreak > nul

echo.
echo [3/3] 检查 Milvus 状态...
docker logs milvus-standalone --tail 5
echo.

echo [OK] Milvus 已就绪！
echo.
echo 访问地址:
echo   - Milvus API: http://localhost:19530
echo   - Milvus Dashboard: http://localhost:9091
echo   - MinIO Console: http://localhost:9001
echo.

pause
