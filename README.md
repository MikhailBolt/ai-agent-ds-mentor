# AI Agent DS Mentor

Telegram bot for learning Data Science with AI.

## Run locally (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# set token (or copy .env.example -> .env)
$env:TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."

python .\main.py
```

## Commands

- `/quiz`: ask a question (answers are plain text messages)
- `/skip`: skip current active question
- `/stats`: show quiz stats
- `/reset`: reset quiz progress
- `/help`: help

## Configuration

Environment variables:
- `TELEGRAM_BOT_TOKEN` (required)
- `LOG_LEVEL` (optional, default `INFO`)
- `DB_PATH` (optional, default `bot.db`)
- `QUESTIONS_PATH` (optional, default `data/questions.json`)
