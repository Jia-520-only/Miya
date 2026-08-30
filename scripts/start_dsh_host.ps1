# ============================================================
#  弥娅 DSH host 启动器（start.bat [1]/[4] 调用）
#  独立进程启动 + 日志落盘 + HTTP 就绪等待（最多 30s）
# ============================================================
param()

$root = Resolve-Path (Join-Path $PSScriptRoot '..')
$port = 3199

$listening = $false
try {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) { $listening = $true }
} catch { }

if (-not $listening) {
    Write-Host "[INFO] Starting DSH host on 127.0.0.1:$port (detached, logged)..."
    $env:DSH_HOME = Join-Path $root 'data\dsh'
    Start-Process -WindowStyle Hidden -FilePath 'node' `
        -ArgumentList (Join-Path $root 'deepseek-harness\apps\cli\lib\bin.js'), 'web', '--host', '127.0.0.1', '--port', "$port" `
        -WorkingDirectory $root `
        -RedirectStandardOutput (Join-Path $root 'logs\dsh_host.log') `
        -RedirectStandardError (Join-Path $root 'logs\dsh_host_err.log')
} else {
    Write-Host "[INFO] DSH host already running on $port"
}

# HTTP 就绪等待（HTTP 200 为准，端口 LISTENING 不算数）
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode) {
            Write-Host "[OK] DSH host ready (${i}s)"
            exit 0
        }
    } catch { }
    Start-Sleep -Seconds 1
}

Write-Host "[WARN] DSH host 30 秒内未 HTTP 就绪，客户端将自动重试"
exit 1
