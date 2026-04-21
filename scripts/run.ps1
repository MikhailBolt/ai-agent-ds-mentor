param(
  [string]$VenvDir = ".venv"
)

$ErrorActionPreference = "Stop"

if (Test-Path "$VenvDir\Scripts\Activate.ps1") {
  & "$VenvDir\Scripts\Activate.ps1"
}

py .\main.py
