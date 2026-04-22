# Contributing

Thanks for your interest in improving this project.

## Setup (Windows / PowerShell)

```powershell
.\scripts\setup.ps1
pip install -r requirements-dev.txt
```

## Run checks locally

```powershell
.\scripts\test.ps1
```

## Pre-commit (recommended)

```powershell
pip install pre-commit
pre-commit install
pre-commit run -a
```

## Code style

- Use `ruff` for linting and formatting.
- Keep functions small and testable (pure helpers in `mentor/` where possible).

