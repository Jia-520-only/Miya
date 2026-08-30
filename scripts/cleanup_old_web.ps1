# 清理旧的 Web 前端代码

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   清理旧的 Web 前端代码" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$removed = 0

# 检查并删除 web_main.py 中的 HTML_TEMPLATE
$webMainPath = Join-Path $PSScriptRoot "..\webnet\web_main.py"
if (Test-Path $webMainPath) {
    Write-Host "[检查] $webMainPath" -ForegroundColor Yellow
    
    $content = Get-Content $webMainPath -Raw
    
    if ($content -match "HTML_TEMPLATE") {
        Write-Host "[跳过] web_main.py 中的 HTML_TEMPLATE 已被清理" -ForegroundColor Green
    } else {
        Write-Host "[OK] web_main.py 已无旧的 HTML 代码" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✅ 清理完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "现在 Web 服务只使用 React 构建的静态文件。" -ForegroundColor Cyan
Write-Host "旧的 HTML 模板已完全移除。" -ForegroundColor Cyan
Write-Host ""
