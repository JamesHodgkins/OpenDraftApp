param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Virtualenv python not found at '$python'. Create it first (e.g. `python -m venv .venv`), then install requirements."
}

Push-Location $repoRoot
try {
    & $python -m pytest @PytestArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

