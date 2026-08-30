param(
    [switch]$Full,
    [switch]$Minimal,
    [switch]$Lightweight,
    [switch]$Dev,
    [switch]$Check,
    [switch]$Upgrade,
    [switch]$Uv,
    [switch]$Yes,
    [switch]$Help,
    [switch]$DryRun
)

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Installer = Join-Path $ProjectRoot "setup\scripts\install.py"
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$Arguments = @()
if ($Uv) { $Arguments += "uv" }
if ($Minimal) { $Arguments += "minimal" }
elseif ($Lightweight) { $Arguments += "lightweight" }
elseif ($Dev) { $Arguments += "dev" }
elseif ($Check) { $Arguments += "check" }
elseif ($Upgrade) { $Arguments += "upgrade" }
elseif ($Help) { $Arguments += "--help" }
else { $Arguments += "full" }
if ($DryRun) { $Arguments += "--dry-run" }

& $Python $Installer @Arguments
exit $LASTEXITCODE
