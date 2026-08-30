# PowerShell Download Script
$ErrorActionPreference = "Stop"

$downloads = @{
    "https://cdn.jsdelivr.net/npm/pixi.js@6.5.10/dist/browser/pixi.min.js" = "pixi.min.js"
    "https://cdn.jsdelivr.net/npm/pixi-live2d-display@0.4.0/dist/index.min.js" = "pixi-live2d-display.min.js"
}

$librariesDir = Join-Path $PSScriptRoot "public\libraries"

if (-not (Test-Path $librariesDir)) {
    New-Item -ItemType Directory -Path $librariesDir -Force | Out-Null
    Write-Host "Create directory: $librariesDir" -ForegroundColor Green
}

Write-Host "`nDownloading Live2D library files...`n" -ForegroundColor Cyan

foreach ($url in $downloads.Keys) {
    $filename = $downloads[$url]
    $filepath = Join-Path $librariesDir $filename

    Write-Host "Downloading: $filename" -ForegroundColor Yellow

    try {
        $progressPreference = 'silentlyContinue'
        Invoke-WebRequest -Uri $url -OutFile $filepath -UseBasicParsing
        Write-Host "OK: $filename downloaded" -ForegroundColor Green
    }
    catch {
        Write-Host "FAIL: $_" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`nAll library files downloaded!" -ForegroundColor Green
Write-Host "Location: $librariesDir`n" -ForegroundColor Cyan
