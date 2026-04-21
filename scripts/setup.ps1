param(
  [string]$VenvDir = ".venv"
)

$ErrorActionPreference = "Stop"

py -m venv $VenvDir
& "$VenvDir\Scripts\Activate.ps1"
py -m pip install --upgrade pip
pip install -r requirements.txt

Write-Host "Setup complete. Activate with: $VenvDir\Scripts\Activate.ps1"
