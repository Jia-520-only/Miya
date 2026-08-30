# 构建弥娅 Web 前端

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   弥娅 Web 前端构建工具" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$webDir = Join-Path $PSScriptRoot "..\frontend\packages\web"

if (-not (Test-Path $webDir)) {
    Write-Host "[错误] Web 前端目录不存在: $webDir" -ForegroundColor Red
    exit 1
}

Write-Host "[1/4] 进入 Web 前端目录..." -ForegroundColor Yellow
Set-Location $webDir

Write-Host "[2/4] 检查 Node.js 和 npm..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version
    $npmVersion = npm --version
    Write-Host "  Node.js: $nodeVersion" -ForegroundColor Green
    Write-Host "  npm: $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "[错误] 未找到 Node.js 或 npm" -ForegroundColor Red
    Write-Host "请先安装 Node.js: https://nodejs.org/" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "[3/4] 安装依赖..." -ForegroundColor Yellow
npm install --loglevel=info --foreground-scripts

if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 依赖安装失败" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[4/4] 构建生产版本..." -ForegroundColor Yellow
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 构建失败" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✅ 构建成功！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "输出目录: $webDir\dist" -ForegroundColor Cyan
Write-Host ""
Write-Host "现在可以启动 Web 服务了：" -ForegroundColor Yellow
Write-Host '  python webnet\web_main.py' -ForegroundColor Cyan
Write-Host ""
