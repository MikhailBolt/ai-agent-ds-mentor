# ai-agent-ds-mentor

AI agent for Telegram that helps users learn Data Science: builds study plans, generates quizzes, evaluates answers, tracks progress, and supports mock interview mode.

## Features

- Telegram bot with long polling
- Personalized study plan generation
- Topic explanations for Data Science subjects
- Quiz mode with hints, skipping, letter-based answers (`A/B/C/D`) and answer review
- Mock interview mode with scored answer review
- Progress tracking and learning statistics
- Daily goals and streak tracking
- Achievements system
- Notes and learning resources
- Daily reminder scheduler
- Health check for Ollama
- Active session status and cancel command
- Local LLM integration through Ollama

## Commands

### Main
- `/start`
- `/help`
- `/profile`
- `/status`
- `/health`
- `/progress`
- `/stats`
- `/daily`
- `/achievements`
- `/streak`

### Setup
- `/setgoal <text>`
- `/setlevel <beginner|junior|middle|advanced>`
- `/settime <minutes>`
- `/notifications on|off`
- `/setlanguage ru|en`

### Learning
- `/plan`
- `/topic <topic>`
- `/topic <topic> <subtopic>`
- `/quiz <topic>`
- `/quiz <topic> <easy|medium|hard>`
- `/answer <option or letter>`
- `/hint`
- `/skip`
- `/challenge`
- `/cancel`

### Mock interview
- `/interview <topic>`
- `/interview_answer <your answer>`
- `/interview_skip`

### Notes and resources
- `/note <title> | <content>`
- `/mynotes`
- `/resources <topic>`

## Setup

### 1. Create a Telegram bot
Create a bot with BotFather and copy the token.

### 2. Install Ollama and model

```bash
ollama run llama3
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env`

```env
TELEGRAM_BOT_TOKEN=your_bot_token
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
DB_PATH=app.db
POLL_INTERVAL_SECONDS=2
LLM_TIMEOUT_SECONDS=120
MAX_RETRIES=3
ENABLE_REMINDERS=true
REMINDER_HOUR=19
DEFAULT_LANGUAGE=ru
DEFAULT_INTERVIEW_QUESTIONS=5
DEFAULT_QUIZ_QUESTIONS=5
```

### 5. Run the bot

```bash
python main.py
```

## Example flow

```text
/start
/setgoal Хочу подготовиться к DS интервью
/setlevel junior
/settime 60
/plan
/topic pandas
/quiz statistics hard
/answer A
/interview machine learning
```

## What this version improves

- safer HTML output in Telegram messages
- answer normalization for quiz options
- session conflict protection
- `/cancel` for active quiz or interview
- `/status` for quick session overview
- `/health` for Ollama availability check
- `/setlanguage` to store preferred language

## Future improvements

- spaced repetition
- skill map by category
- weekly reports
- webhook mode instead of polling
- export progress summary to markdown or PDF
