# Changelog

## 0.4.3 (2026-05-14)

- **Меньше повторов**: приоритет вопросам, которые вы ещё не встречали (`question_history`)
- **Лучшая серия** (`best_streak`) в статистике и `/status`
- **`/progress`** — алиас `/stats` с прогрессом по банку (встречено X/Y)
- Сообщение при полном прохождении банка; пометка «Повтор вопроса»
- **+3 вопроса** (21 в банке)

## 0.4.2 (2026-05-14)

- **`/practice`** (и `/weak`) — вопрос по самой слабой или ещё не пройденной теме
- **`/topics`** — компактный список id тем и размер банка
- **Пояснения** (`explanation`) в банке — показываются после неверного ответа
- **`/map`**: число вопросов в банке по теме, id для `/quiz`
- **Меню команд** Telegram (`setMyCommands` при старте)
- **+3 вопроса** (18 в банке)

## 0.4.1 (2026-05-14)

- **`/hint`** — подсказка к активному вопросу без завершения сессии
- **Расширенная `/stats`**: серия верных, прогресс по темам, рекомендация что подтянуть
- **Серия ответов** (streak) в SQLite; бонусы на 3 / 5 / 10 подряд
- **+4 вопроса** в банке (15 всего); подсказки для статистики
- **`mentor check`**: проверка, что у каждой компетенции есть хотя бы один вопрос

## 0.4.0 (2026-05-14)

- **Карта компетенций**: `mentor/data/competencies.json`, команда `/map`
- **Улучшенный банк вопросов**: темы, сложность 1–3, подсказки; 11 вопросов
- **Квиз по теме**: `/quiz ml-metrics` (и другие id из карты)
- **Умный выбор вопроса**: приоритет слабым/непройденным компетенциям
- **Прогресс по темам** в SQLite (`competency_stats`)

## 0.3.4 (2026-05-14)

- CLI: `mentor check --verify-db` validates SQLite schema (pairs with `--init-db`)
- DB: `verify_schema()` helper for required tables

## 0.3.3 (2026-05-13)

- CLI: load `.env` before `check` / `run` (token and paths from file work without manual export)
- CLI: `check --print-config` includes `project_repo_url`
- Bot: `/status` shows active quiz question id when one is pending

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
