# PowerShell script to install desktop dependencies with explicit directory handling

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "      安装弥娅桌面端依赖" -ForegroundColor Cyan
Write-Host "      Miya Desktop Dependencies" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 设置工作目录
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktopDir = Join-Path $scriptDir "miya-desktop"

Write-Host "脚本目录: $scriptDir" -ForegroundColor Yellow
Write-Host "桌面端目录: $desktopDir" -ForegroundColor Yellow
Write-Host ""

if (-not (Test-Path $desktopDir)) {
    Write-Host "错误: 桌面端目录不存在: $desktopDir" -ForegroundColor Red
    exit 1
}

try {
    Set-Location $desktopDir
    Write-Host "当前工作目录:" -ForegroundColor Green
    Get-Location
    Write-Host ""

    # 检查package.json
    if (-not (Test-Path "package.json")) {
        Write-Host "错误: package.json 不存在" -ForegroundColor Red
        exit 1
    }

    Write-Host "找到 package.json" -ForegroundColor Green
    Write-Host ""

    Write-Host "正在运行: npm install" -ForegroundColor Cyan
    Write-Host "这可能需要几分钟..." -ForegroundColor Yellow
    Write-Host ""

    # 运行npm install
    $result = & npm install 2>&1
    $exitCode = $LASTEXITCODE

    Write-Output $result

    if ($exitCode -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "      依赖安装成功!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "现在可以启动桌面端了:" -ForegroundColor Cyan
        Write-Host "  start.bat (选择选项4)" -ForegroundColor White
        Write-Host "  start_desktop.bat" -ForegroundColor White
        Write-Host "  python run/desktop_main.py" -ForegroundColor White
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Red
        Write-Host "      依赖安装失败" -ForegroundColor Red
        Write-Host "========================================" -ForegroundColor Red
        Write-Host ""
        Write-Host "错误代码: $exitCode" -ForegroundColor Red
        Write-Host ""
        Write-Host "可能的解决方案:" -ForegroundColor Yellow
        Write-Host "1. 清理npm缓存: npm cache clean --force" -ForegroundColor White
        Write-Host "2. 手动在miya-desktop目录运行: npm install" -ForegroundColor White
        Write-Host "3. 使用淘宝镜像: npm config set registry https://registry.npmmirror.com" -ForegroundColor White
        Write-Host ""
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "      发生错误" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "错误信息: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    exit 1
}

Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
