# ============================================================
#  弥娅 DSH TUI 启动器（start.bat [1] 在 Windows Terminal 中调用）
#  自动加载 API Key、连接失败自动重试 3 次、日志落盘
# ============================================================
param()

$root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $root

$logFile = Join-Path $root 'logs\tui_launch.log'
$env:DSH_HOME = Join-Path $root 'data\dsh'
$env:DSH_URL = 'http://127.0.0.1:3199'

# 从 config\.env 加载 DeepSeek API Key（进程环境优先）
if (-not $env:DEEPSEEK_API_KEY) {
    $envPath = Join-Path $root 'config\.env'
    if (Test-Path $envPath) {
        foreach ($line in [System.IO.File]::ReadAllLines($envPath)) {
            $line = $line.Trim()
            if (-not $line -or $line.StartsWith('#')) { continue }
            $idx = $line.IndexOf('=')
            if ($idx -le 0) { continue }
            $k = $line.Substring(0, $idx).Trim()
            $v = $line.Substring($idx + 1).Trim()
            if ($k -eq 'DEEPSEEK_API_KEY' -and $v) { $env:DEEPSEEK_API_KEY = $v }
        }
    }
}

$tui = Join-Path $PSScriptRoot 'node_modules\dsh-tui\bin\tui.js'
if (-not (Test-Path $tui)) {
    Write-Host "[ERROR] dsh-tui 未安装，请执行: cd tools\dsh-tui && npm install dsh-tui"
    Read-Host '按回车关闭'
    exit 1
}

"[$([DateTime]::Now)] TUI start (cwd=$root)" | Add-Content $logFile -Encoding UTF8

$maxTries = 3
for ($i = 1; $i -le $maxTries; $i++) {
    & node $tui
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        "[$([DateTime]::Now)] TUI exited code=0" | Add-Content $logFile -Encoding UTF8
        exit 0
    }
    "[$([DateTime]::Now)] TUI attempt $i failed code=$code" | Add-Content $logFile -Encoding UTF8
    if ($i -lt $maxTries) {
        Write-Host "[INFO] 连接失败，2 秒后重试 ($i/$maxTries)..."
        Start-Sleep -Seconds 2
    }
}

Write-Host ""
Write-Host "[ERROR] dsh-tui 连续 $maxTries 次启动失败"
Write-Host "日志: logs\tui_launch.log / logs\dsh_host_err.log"
Read-Host '按回车关闭'
exit 1
