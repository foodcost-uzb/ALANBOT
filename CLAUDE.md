# ALANBOT — Telegram Daily Checklist Bot

## Stack
- Python 3.9+ (uses `from __future__ import annotations` for type hints)
- aiogram 3.x (async Telegram bot framework)
- aiosqlite (async SQLite)
- APScheduler (task scheduling)

## Running
```bash
pip install -r requirements.txt
cp .env.example .env  # fill in BOT_TOKEN and PARENT_PASSWORD
python -m bot.main
```

## Project structure
- `bot/config.py` — env variables (BOT_TOKEN, TIMEZONE, hours, password)
- `bot/tasks_config.py` — fixed daily tasks, scoring constants, money tiers, motivational messages
- `bot/scoring.py` — pure scoring functions (daily/weekly points, money %, deficit calc, summaries)
- `bot/database.py` — DB init, migrations, completions + extra_tasks + family password queries
- `bot/keyboards.py` — inline keyboards (role selection, checklist with extras, child picker)
- `bot/handlers/start.py` — /start, role selection, password-protected parent registration
- `bot/handlers/parent.py` — /today, /invite, /report, /history, /extra, /password
- `bot/handlers/child.py` — /checklist, photo confirmation FSM, toggle, extra task support
- `bot/scheduler.py` — morning checklist (7:00), reminders (12:00, 17:00), evening summary (21:00), weekly report (Sun 20:00)
- `bot/main.py` — entry point

## Commands
### Parent
- `/today` — child's progress for today
- `/report` — current week report with money %
- `/history` — reports for last 4 weeks
- `/extra` — assign bonus task to child (with child picker for multi-child)
- `/invite` — show invite code
- `/password` — change registration password

### Child
- `/checklist` — today's task list with photo confirmation

## Scoring system
- 8 fixed daily tasks (1 point each): teeth, clothes, bed, shower, underwear, laundry, prep, tidy
- Shower rule: if shower not done, entire day = 0 points
- Sunday: extra task "room_clean" — if not done, -5 penalty from weekly total
- Extra tasks: parent-assigned bonus points (added on top of daily points)
- Weekly money tiers: 50-56 → 100%, 42-49 → 70%, 35-41 → 40%, <35 → 0%

## Scheduler
- 7:00 — morning checklist to all children
- 12:00, 17:00 — motivational reminders if tasks incomplete
- 21:00 — evening summary to parents + child (with deficit to next tier)
- Sunday 20:00 — weekly report to parents

## Database tables
- `families` — id, invite_code, parent_password
- `users` — id, telegram_id, role, family_id, name
- `completions` — child_id, task_key, date, photo_file_id (fixed tasks)
- `extra_tasks` — family_id, child_id, title, points, date, completed, photo_file_id

## Conventions
- All text in Russian (user-facing)
- FSM states via aiogram StatesGroup
- Inline keyboards for all interactions
- SQLite DB stored in data/bot.db
- Fixed tasks defined in tasks_config.py; extra tasks stored in DB
- Photo confirmation required for all task completions
