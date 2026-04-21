param(
  [string]$VenvDir = ".venv"
)

$ErrorActionPreference = "Stop"

if (Test-Path "$VenvDir\Scripts\Activate.ps1") {
  & "$VenvDir\Scripts\Activate.ps1"
}

pip install -r requirements-dev.txt
py -m ruff check .
py -m ruff format --check .
py -m pytest -q
