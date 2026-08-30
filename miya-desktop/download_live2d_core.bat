@echo off
chcp 65001 >nul
echo ========================================
echo 下载 Live2D Cubism Core
echo ========================================
echo.

echo 正在打开 Live2D 官网下载页面...
echo.

start https://www.live2d.com/zh-CHS/download/cubism-sdk/download-web/

echo.
echo ========================================
echo 下载步骤:
echo ========================================
echo.
echo 1. 在打开的页面中，勾选同意条款
echo 2. 填写邮箱（可选）
echo 3. 点击"下载"按钮
echo 4. 下载 "Cubism Core for Web"
echo 5. 解压下载的压缩包
echo 6. 找到 Core/live2dcubismcore.min.js 文件
echo 7. 复制到: public\live2d\script\live2dcubismcore.min.js
echo.
echo ========================================
echo 下载完成后，运行以下命令:
echo.
echo npm run dev
echo.
echo ========================================
pause
