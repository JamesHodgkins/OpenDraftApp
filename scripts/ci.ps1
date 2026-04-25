param(
  [string]$Python = "3.11",
  [string]$VenvDir = ".venv-ci"
)

$ErrorActionPreference = "Stop"

function Assert-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Required command not found: $name"
  }
}

Assert-Command "py"

Write-Host "==> Using Python $Python"
py -$Python -V

if (-not (Test-Path $VenvDir)) {
  Write-Host "==> Creating venv $VenvDir"
  py -$Python -m venv $VenvDir
}

$Py = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $Py)) {
  throw "Venv python not found at $Py"
}

Write-Host "==> Installing dependencies"
& $Py -m pip install -U pip | Out-Host
& $Py -m pip install -r requirements.txt pyright | Out-Host

Write-Host "==> Running pytest (CI flags)"
$env:QT_QPA_PLATFORM = "minimal"
$env:QT_OPENGL = "software"
$env:LIBGL_ALWAYS_SOFTWARE = "1"
$env:PYTHONFAULTHANDLER = "1"
$env:PYTHONUNBUFFERED = "1"
$env:XDG_RUNTIME_DIR = (Join-Path (Get-Location) ".xdg-runtime")
New-Item -ItemType Directory -Force $env:XDG_RUNTIME_DIR | Out-Null

& $Py -m pytest -ra -vv --maxfail=1

Write-Host "==> Running pyright (CI parity: force pythonpath)"
& (Join-Path $VenvDir "Scripts\pyright.exe") --pythonpath $Py
