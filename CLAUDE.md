# ALANBOT — Telegram Daily Checklist Bot + Mini App

## Stack
- Python 3.9+ (uses `from __future__ import annotations` for type hints)
- aiogram 3.x (async Telegram bot framework)
- aiosqlite (async SQLite, WAL mode for concurrent access)
- APScheduler (task scheduling)
- aiohttp (Mini App web API server)

## Running

### Bot
```bash
pip install -r requirements.txt
cp .env.example .env  # fill in BOT_TOKEN and PARENT_PASSWORD
python -m bot.main
```

### Mini App (Web API)
```bash
python -m webapp.server  # starts on port 8081 (WEBAPP_PORT)
```

Both processes share one SQLite DB (`data/bot.db`) via WAL mode.

## Project structure

### Bot (Telegram)
- `bot/config.py` — env variables (BOT_TOKEN, TIMEZONE, hours, password)
- `bot/tasks_config.py` — fixed daily tasks, scoring constants, money tiers, motivational messages
- `bot/scoring.py` — pure scoring functions (daily/weekly points, money %, deficit calc, summaries)
- `bot/database.py` — DB init, migrations, completions + extra_tasks + family password queries
- `bot/keyboards.py` — inline keyboards (role selection, checklist with extras, child picker, task manager, approvals)
- `bot/child_tasks.py` — per-child task helpers (active tasks, shower check, labels)
- `bot/handlers/start.py` — /start, role selection, password-protected parent registration
- `bot/handlers/parent.py` — /today, /children, /invite, /report, /history, /extra, /tasks, /password, approval callbacks
- `bot/handlers/child.py` — /checklist, photo/video confirmation FSM, toggle, extra task support
- `bot/scheduler.py` — morning checklist (7:00), reminders (12:00, 17:00), evening summary (21:00), weekly report (Sun 20:00)
- `bot/main.py` — entry point

### Mini App (Web)
- `webapp/server.py` — aiohttp entry point, static serving, SPA fallback
- `webapp/auth.py` — Telegram initData HMAC-SHA256 validation middleware
- `webapp/db.py` — standalone DB connection (WAL mode, imports `bot.scoring` + `bot.tasks_config`)
- `webapp/notify.py` — Telegram Bot API HTTP calls (sendMessage, getFile)
- `webapp/routes/auth_routes.py` — `GET /api/me`
- `webapp/routes/child_routes.py` — checklist, photo upload, uncomplete, extras, media proxy
- `webapp/routes/parent_routes.py` — children, today, report, history, approvals, extras, tasks, invite

### Frontend (Vanilla JS SPA)
- `webapp/static/index.html` — SPA shell + Telegram WebApp SDK
- `webapp/static/css/style.css` — mobile-first CSS with Telegram theme vars
- `webapp/static/js/api.js` — fetch wrapper with `Authorization: tma <initData>`
- `webapp/static/js/app.js` — router, nav setup, Telegram.WebApp.ready()
- `webapp/static/js/views/checklist.js` — child: task groups, photo capture, upload
- `webapp/static/js/views/parent-today.js` — parent: dashboard + child progress
- `webapp/static/js/views/parent-report.js` — parent: weekly report table
- `webapp/static/js/views/parent-history.js` — parent: last 4 weeks
- `webapp/static/js/views/parent-approvals.js` — parent: approve/reject with media preview
- `webapp/static/js/views/parent-extras.js` — parent: assign bonus task
- `webapp/static/js/views/parent-tasks.js` — parent: toggle/add/delete/reset tasks

### Deploy
- `deploy/alanbot-web.service` — systemd unit for Mini App
- `deploy/nginx-webapp.conf` — nginx reverse proxy with SSL
- `deploy/auto-deploy.sh` — auto-deploy both bot + web to Contabo VPS

## API Endpoints

### Auth
- `GET /api/me` — current user info (id, role, family_id, name)

### Child
- `GET /api/checklist` — today's tasks + extras with statuses
- `POST /api/checklist/{task_key}/complete` — upload photo (multipart)
- `POST /api/checklist/{task_key}/uncomplete` — cancel completion
- `POST /api/extras/{extra_id}/complete` — photo for bonus task
- `POST /api/extras/{extra_id}/uncomplete` — cancel bonus
- `GET /api/media/{file_id}` — proxy Telegram file or serve local upload

### Parent
- `GET /api/children` — children with progress + pending approval count
- `GET /api/today/{child_id}` — today's detail
- `GET /api/report/{child_id}` — weekly report
- `GET /api/history/{child_id}` — last 4 weeks
- `GET /api/approvals` — pending approvals queue
- `POST /api/approvals/{id}/approve` — approve (body: `{"type":"task"|"extra"}`)
- `POST /api/approvals/{id}/reject` — reject
- `POST /api/extras` — assign bonus (body: `{"child_id", "title", "points"}`)
- `GET /api/tasks/{child_id}` — task configuration
- `POST /api/tasks/{child_id}/toggle` — enable/disable (body: `{"task_key", "enabled"}`)
- `POST /api/tasks/{child_id}/add` — add custom (body: `{"label"}`)
- `POST /api/tasks/{child_id}/delete` — delete custom (body: `{"task_key"}`)
- `POST /api/tasks/{child_id}/reset` — reset to defaults
- `GET /api/invite` — family invite code

## Commands
### Parent
- `/today` — child's progress for today
- `/children` — list children with task progress
- `/report` — current week report with money %
- `/history` — reports for last 4 weeks
- `/extra` — assign bonus task to child (with child picker for multi-child)
- `/tasks` — manage child's checklist (enable/disable/add/remove tasks)
- `/invite` — show invite code
- `/password` — change registration password

### Child
- `/checklist` — today's task list with photo/video confirmation

## Scoring system
- 8 fixed daily tasks (1 point each): teeth, clothes, bed, shower, underwear, laundry, prep, tidy
- Per-child customization: parents can enable/disable standard tasks and add custom ones
- Shower rule: if shower not done (and enabled), entire day = 0 points
- Sunday: extra task "room_clean" — if not done, -5 penalty from weekly total
- Extra tasks: parent-assigned bonus points (added on top of daily points)
- Weekly money tiers: 50-56 → 100%, 42-49 → 70%, 35-41 → 40%, <35 → 0%

## Approval workflow
- All task completions require photo/video confirmation
- Submitted tasks get status "pending" (🕐) — `approved = 0`
- Parents approve (✅ → `approved = 1`) or reject (❌ → record deleted)
- Only approved tasks count toward scoring
- Telegram notifications sent to parents on submission, to children on approve/reject

## Scheduler
- 7:00 — morning checklist to all children
- 12:00, 17:00 — motivational reminders if tasks incomplete
- 21:00 — evening summary to parents + child (with deficit to next tier)
- Sunday 20:00 — weekly report to parents

## Database tables
- `families` — id, invite_code, parent_password
- `users` — id, telegram_id, role, family_id, name
- `completions` — child_id, task_key, date, photo_file_id, approved, media_type
- `extra_tasks` — family_id, child_id, title, points, date, completed, photo_file_id, approved, media_type
- `child_tasks` — child_id, task_key, label, task_group, is_standard, enabled, sort_order

## Photo storage
- Bot: stores Telegram `file_id` strings in DB
- Mini App: saves files to `data/uploads/{date}/{uuid}.{ext}`, stores path in DB
- `GET /api/media/{file_id}` detects type by prefix: `uploads/` → local file, otherwise → proxy via Telegram Bot API getFile

## Conventions
- All text in Russian (user-facing)
- FSM states via aiogram StatesGroup
- Inline keyboards for all interactions
- SQLite DB stored in data/bot.db (WAL mode)
- Fixed tasks defined in tasks_config.py; extra tasks and per-child configs in DB
- Photo/video confirmation required for all task completions
