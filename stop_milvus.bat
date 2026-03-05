@echo off
REM ============================================
REM Milvus 数据库停止脚本
REM ============================================

echo [1/2] 停止 Milvus 相关服务...
docker-compose -f docker-compose.milvus.yml down

echo.
echo [2/2] 检查容器状态...
docker ps -a | findstr milvus

echo.
echo [OK] Milvus 已停止
echo.
pause
