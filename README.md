# AI Agent DS Mentor

[![CI](https://github.com/MikhailBolt/ai-agent-ds-mentor/actions/workflows/ci.yml/badge.svg)](https://github.com/MikhailBolt/ai-agent-ds-mentor/actions)

Telegram bot that runs a **Data Science quiz** from a JSON question bank, tracks progress in **SQLite**, and uses the Telegram Bot API (**long polling**).

**Stack:** Python 3.11+, `requests`, `python-dotenv`, SQLite (`sqlite3`).

## Features

- Commands: `/quiz`, `/skip`, `/cancel`, `/stats`, `/reset`, `/help`
- Normalizes `/cmd@BotUsername` (Telegram menu / groups)
- Retries on HTTP 429 using `Retry-After`
- Quiz answers: exact match or substring match for long reference answers

## Project layout

```
main.py              # entrypoint, Telegram polling
mentor/
  db.py              # SQLite schema + user stats
  quiz.py            # questions JSON + matching
  textutil.py        # command parsing (unit-tested)
data/questions.json
tests/               # pytest
```

## Run locally (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# copy .env.example -> .env and set TELEGRAM_BOT_TOKEN
# or:
$env:TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."

py .\main.py
```

## Tests & CI

```powershell
pip install -r requirements-dev.txt
pytest -q
```

GitHub Actions runs the same on every push/PR to `main` (see `.github/workflows/ci.yml`).

## Configuration

| Variable | Required | Default |
|----------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | yes | — |
| `LOG_LEVEL` | no | `INFO` |
| `DB_PATH` | no | `bot.db` |
| `QUESTIONS_PATH` | no | `data/questions.json` |

## License

MIT — see [LICENSE](LICENSE).
