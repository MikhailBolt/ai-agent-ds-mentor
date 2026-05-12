# Changelog

## 0.3.2 (2026-05-09)

- Bot: `/about` (version + repo link; override via `PROJECT_REPO_URL`)
- Repo: `.gitattributes` for consistent line endings (fewer CRLF warnings on Windows)

## 0.3.1 (2026-05-09)

- Startup logs: version, paths, question count, log level (no secrets)
- `mentor check --print-config`: includes `log_level`
- `pyproject.toml`: `[project.urls]` (Homepage, Repository, Changelog)

## 0.3.0 (2026-05-09)

- CLI: `mentor check` with `--print-config`, `--init-db`, `--db-path`
- CLI: `run --dry-run` aligned with `check` (incl. custom `--token-env`)
- Telegram: long message chunking, edited messages, update de-duplication
- Packaging: single version source (`mentor._version`), Dependabot, Docker `pip install .`

## 0.2.0

- SQLite-backed quiz, Ruff + pytest + CI, packaged question bank under `mentor/data/`
