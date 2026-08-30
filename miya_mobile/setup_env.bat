@echo off
setlocal enabledelayedexpansion
REM ========================================
REM 弥娅手机APP - 环境配置脚本 (Windows)
REM ========================================

echo.
echo   ◆ 弥娅手机APP 环境检查
echo   ────────────────────────────

REM 检查 JDK
set JAVA_VER=
for /f "tokens=3" %%v in ('java -version 2^>^&1 ^| findstr /i "version"') do set JAVA_VER=%%v
if defined JAVA_VER (
    echo   [OK] JDK: !JAVA_VER!
) else (
    echo   [FAIL] JDK 未找到，正在安装...
    winget install Microsoft.OpenJDK.17 --accept-package-agreements --accept-source-agreements
    echo   请重新打开终端以使 JDK 生效
    pause
    exit /b
)

REM 检查 Android SDK
if defined ANDROID_HOME (
    echo   [OK] ANDROID_HOME: !ANDROID_HOME!
) else (
    set "DEFAULT_SDK=%LOCALAPPDATA%\Android\Sdk"
    if exist "!DEFAULT_SDK!" (
        echo   [OK] 找到 SDK: !DEFAULT_SDK!
        setx ANDROID_HOME "!DEFAULT_SDK!" >nul
    ) else (
        echo   [WARN] Android SDK 未找到
        echo   请安装 Android Studio: https://developer.android.com/studio
        echo   或下载命令行工具: https://developer.android.com/studio#command-line-tools-only
    )
)

REM 检查 Android Studio
if exist "%ProgramFiles%\Android\Android Studio\bin\studio64.exe" (
    echo   [OK] Android Studio 已安装
) else (
    echo   [INFO] Android Studio 未安装 (可选，推荐)
)

echo   ────────────────────────────
echo   环境检查完成！
echo.
echo   启动 Android Studio 开发:
echo     → 用 Android Studio 打开 miya_mobile/ 目录
echo     → 等待 Gradle Sync 完成
echo     → Run 'androidApp'
echo.
echo   启动弥娅后端测试:
echo     → cd D:\AI_MIYA_Factory\MIYA\Miya
echo     → python run/daemon.py --api-port 9800
echo.

pause
