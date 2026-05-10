# Changelog

## 0.3.0 (2026-05-09)

- CLI: `mentor check` with `--print-config`, `--init-db`, `--db-path`
- CLI: `run --dry-run` aligned with `check` (incl. custom `--token-env`)
- Telegram: long message chunking, edited messages, update de-duplication
- Packaging: single version source (`mentor._version`), Dependabot, Docker `pip install .`

## 0.2.0

- SQLite-backed quiz, Ruff + pytest + CI, packaged question bank under `mentor/data/`
