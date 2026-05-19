# AI Agent DS Mentor

[![CI](https://github.com/MikhailBolt/ai-agent-ds-mentor/actions/workflows/ci.yml/badge.svg)](https://github.com/MikhailBolt/ai-agent-ds-mentor/actions)

Telegram bot that runs a **Data Science quiz** from a JSON question bank, tracks progress in **SQLite**, and uses the Telegram Bot API (**long polling**).

**Stack:** Python 3.11+, `requests`, `python-dotenv`, SQLite (`sqlite3`).

## Features

- Commands: `/quiz`, `/practice`, `/review`, `/map`, `/topics`, `/hint`, `/explain`, `/skip`, `/stats`, `/progress`, `/status`, `/about`, `/reset`, `/help`
- **Competency map** (`/map`) with per-topic progress bars
- Smarter quizzes: unseen-first; difficulty filter; `/review` missed questions; `/explain`; safe `/reset confirm`
- Telegram command menu registered on startup (`setMyCommands`)
- `/stats` shows per-topic progress and what to practice next
- Normalizes `/cmd@BotUsername` (Telegram menu / groups)
- Retries on HTTP 429 using `Retry-After`
- Quiz answers: exact match or substring match for long reference answers
- De-duplicates Telegram update retries and handles edited messages without double-counting stats

## Project layout

```
main.py              # entrypoint, Telegram polling
mentor/
  db.py              # SQLite schema + user stats
  quiz.py            # questions JSON + matching
  textutil.py        # command parsing (unit-tested)
  data/questions.json      # question bank (competency_id, difficulty, hint)
  data/competencies.json   # competency map
tests/               # pytest
```

## Run locally (Windows / PowerShell)

Quickstart scripts:

```powershell
.\scripts\setup.ps1

# set token (or copy .env.example -> .env)
$env:TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."

.\scripts\run.ps1
```

Manual:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# copy .env.example -> .env and set TELEGRAM_BOT_TOKEN
# or:
$env:TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."

py -m mentor
```

## Quick checks (no token)

Show version:

```powershell
py -m mentor --version
```

Validate the question bank (useful in CI). The CLI loads `.env` from the current directory first (same as `run`).

```powershell
py -m mentor check --skip-token
```

Print resolved config (helpful for debugging):

```powershell
py -m mentor check --skip-token --print-config
```

Initialize DB schema (optional):

```powershell
py -m mentor check --skip-token --init-db --db-path bot.db
```

Verify schema on an existing database:

```powershell
py -m mentor check --skip-token --verify-db --db-path bot.db
```

If your token lives under a custom env var name (for example `BOT_TOKEN`), start the bot with:

```powershell
py -m mentor --token-env BOT_TOKEN
```

Dry-run (validate config without starting polling):

```powershell
py -m mentor run --dry-run
```

With a custom token env var name, put global flags **before** the subcommand:

```powershell
py -m mentor --token-env MY_BOT_TOKEN run --dry-run
```

Note: duplicate `id` values in the questions JSON are rejected at load time.

## Install as a package (editable)

```powershell
pip install -e .
mentor --version
mentor check --skip-token
```

## Run with Docker

```powershell
docker build -t ai-agent-ds-mentor .
docker run --rm -e TELEGRAM_BOT_TOKEN="123456:ABC-DEF..." ai-agent-ds-mentor
```

## Tests & CI

```powershell
pip install -r requirements-dev.txt
pytest -q
```

Or:

```powershell
.\scripts\test.ps1
```

GitHub Actions runs the same on every push/PR to `main` (see `.github/workflows/ci.yml`).

## Development notes

- Optional (recommended): enable `pre-commit` hooks

```powershell
pip install pre-commit
pre-commit install
```

See `CONTRIBUTING.md` for details.

## Configuration

| Variable | Required | Default |
|----------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | yes | — |
| `LOG_LEVEL` | no | `INFO` |
| `DB_PATH` | no | `bot.db` |
| `QUESTIONS_PATH` | no | packaged `mentor/data/questions.json` |
| `COMPETENCIES_PATH` | no | packaged `mentor/data/competencies.json` |
| `PROJECT_REPO_URL` | no | default GitHub repo URL (shown in `/about`) |

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
