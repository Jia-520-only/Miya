@echo off
REM 快速安装缺失的依赖

echo 正在安装缺失的依赖包...

pip install PyPDF2>=3.0.0
pip install pypdfium2>=1.0.0

echo.
echo 依赖安装完成！
pause
