# ALANBOT — Telegram Daily Checklist Bot

## Stack
- Python 3.10+
- aiogram 3.x (async Telegram bot framework)
- aiosqlite (async SQLite)
- APScheduler (task scheduling)

## Running
```bash
pip install -r requirements.txt
cp .env.example .env  # fill in BOT_TOKEN
python -m bot.main
```

## Project structure
- `bot/config.py` — env variables, paths
- `bot/tasks_config.py` — fixed daily tasks, scoring constants, money tiers
- `bot/scoring.py` — pure scoring functions (daily points, weekly report, money %)
- `bot/database.py` — DB init + completion queries
- `bot/keyboards.py` — inline keyboards (role selection, checklist)
- `bot/handlers/start.py` — /start, role selection, registration FSM
- `bot/handlers/parent.py` — /today, /invite, /report
- `bot/handlers/child.py` — /checklist, tap-to-toggle task completion
- `bot/scheduler.py` — morning checklist, evening summary, weekly report
- `bot/main.py` — entry point

## Scoring system
- 8 fixed daily tasks (1 point each): teeth, clothes, bed, shower, underwear, laundry, prep, tidy
- Shower rule: if shower not done, entire day = 0 points
- Sunday: extra task "room_clean" — if not done, -5 penalty from weekly total
- Weekly money tiers: 50-56 → 100%, 42-49 → 70%, 35-41 → 40%, <35 → 0%

## Conventions
- All text in Russian (user-facing)
- FSM states via aiogram StatesGroup
- Inline keyboards for all interactions
- SQLite DB stored in data/bot.db
- Tasks are fixed (not user-created) — defined in tasks_config.py
