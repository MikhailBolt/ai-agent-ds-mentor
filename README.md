# ai-agent-ds-mentor

AI agent for Telegram that helps users learn Data Science: builds study plans, generates quizzes, evaluates answers, tracks progress, and now supports mock interview mode.

## Features

- Telegram bot with long polling
- Personalized study plan generation
- Topic explanations for Data Science subjects
- Quiz mode with hints, skipping, and answer review
- Mock interview mode with scored answer review
- Progress tracking and learning statistics
- Daily goals and streak tracking
- Achievements system
- Notes and learning resources
- Daily reminder scheduler
- Local LLM integration through Ollama

## Tech stack

- Python
- Requests
- SQLite
- APScheduler
- Ollama

## Project structure

```text
ai-agent-ds-mentor/
├── main.py
├── README.md
├── requirements.txt
└── .env.example
```

## Setup

### 1. Create a Telegram bot
Create a bot with BotFather and copy the token.

### 2. Install Ollama and model
Run a local model, for example:

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
```

### 5. Run the bot

```bash
python main.py
```

## Commands

### Main
- `/start`
- `/help`
- `/profile`
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

### Learning
- `/plan`
- `/topic <topic>`
- `/topic <topic> <subtopic>`
- `/quiz <topic>`
- `/quiz <topic> <easy|medium|hard>`
- `/answer <option>`
- `/hint`
- `/skip`
- `/challenge`

### Mock interview
- `/interview <topic>`
- `/interview_answer <your answer>`
- `/interview_skip`

### Notes and resources
- `/note <title> | <content>`
- `/mynotes`
- `/resources <topic>`

## Example flow

```text
/start
/setgoal Хочу подготовиться к DS интервью
/setlevel junior
/settime 60
/plan
/topic pandas
/quiz statistics hard
/interview machine learning
```

## What the project demonstrates

- Agent-style orchestration with separate planning, tutoring, quiz, review, interview, and progress logic
- Practical Telegram bot development
- Persistent user state with SQLite
- Adaptive learning workflows
- Local AI product integration with Ollama

## Future improvements

- spaced repetition
- richer topic taxonomy
- skill map by category
- weekly reports
- webhook mode instead of polling
- export progress summary to markdown or PDF
