from __future__ import annotations

import random
import string
from datetime import date, datetime, timedelta

import aiosqlite

from .config import DB_PATH
from .tasks_config import DAILY_TASKS, SUNDAY_TASK

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys = ON")
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


async def init_db() -> None:
    db = await get_db()

    # Migration: drop old tasks-based schema if it exists
    rows = await db.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
    )
    if rows:
        await db.executescript(
            """
            DROP TABLE IF EXISTS completions;
            DROP TABLE IF EXISTS tasks;
            """
        )
        await db.commit()

    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS families (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invite_code TEXT UNIQUE NOT NULL,
            parent_password TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('parent', 'child')),
            family_id INTEGER REFERENCES families(id),
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS extra_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            family_id INTEGER NOT NULL REFERENCES families(id),
            child_id INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 1,
            date TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            photo_file_id TEXT,
            approved INTEGER NOT NULL DEFAULT 0,
            media_type TEXT DEFAULT 'photo'
        );

        CREATE TABLE IF NOT EXISTS completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id INTEGER NOT NULL REFERENCES users(id),
            task_key TEXT NOT NULL,
            date TEXT NOT NULL,
            photo_file_id TEXT,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved INTEGER NOT NULL DEFAULT 0,
            media_type TEXT DEFAULT 'photo',
            UNIQUE(child_id, task_key, date)
        );

        CREATE TABLE IF NOT EXISTS child_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id INTEGER NOT NULL REFERENCES users(id),
            task_key TEXT NOT NULL,
            label TEXT NOT NULL,
            task_group TEXT NOT NULL DEFAULT 'custom',
            is_standard INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            UNIQUE(child_id, task_key)
        );
        """
    )

    # Migrations for existing databases: add approved and media_type columns
    for table in ("completions", "extra_tasks"):
        cols = await db.execute_fetchall(f"PRAGMA table_info({table})")
        col_names = {c["name"] for c in cols}
        if "approved" not in col_names:
            await db.execute(
                f"ALTER TABLE {table} ADD COLUMN approved INTEGER NOT NULL DEFAULT 0"
            )
        if "media_type" not in col_names:
            await db.execute(
                f"ALTER TABLE {table} ADD COLUMN media_type TEXT DEFAULT 'photo'"
            )

    await db.commit()


# ── Families ──────────────────────────────────────────────


def _generate_invite_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


async def create_family() -> tuple[int, str]:
    db = await get_db()
    code = _generate_invite_code()
    cursor = await db.execute(
        "INSERT INTO families (invite_code) VALUES (?)", (code,)
    )
    await db.commit()
    return cursor.lastrowid, code


async def get_family_by_invite(code: str) -> dict | None:
    db = await get_db()
    row = await db.execute_fetchall(
        "SELECT * FROM families WHERE invite_code = ?", (code.upper(),)
    )
    if row:
        return dict(row[0])
    return None


async def get_family_invite_code(family_id: int) -> str | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT invite_code FROM families WHERE id = ?", (family_id,)
    )
    if rows:
        return rows[0]["invite_code"]
    return None


# ── Users ─────────────────────────────────────────────────


async def create_user(
    telegram_id: int, role: str, family_id: int, name: str
) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO users (telegram_id, role, family_id, name) VALUES (?, ?, ?, ?)",
        (telegram_id, role, family_id, name),
    )
    await db.commit()
    return cursor.lastrowid


async def get_user(telegram_id: int) -> dict | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
    )
    if rows:
        return dict(rows[0])
    return None


async def get_family_parents(family_id: int) -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM users WHERE family_id = ? AND role = 'parent'", (family_id,)
    )
    return [dict(r) for r in rows]


async def get_family_children(family_id: int) -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM users WHERE family_id = ? AND role = 'child'", (family_id,)
    )
    return [dict(r) for r in rows]


async def get_user_by_id(user_id: int) -> dict | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    )
    if rows:
        return dict(rows[0])
    return None


# ── Completions ───────────────────────────────────────────


async def complete_task(
    child_id: int,
    task_key: str,
    today: str,
    photo_file_id: str | None = None,
    media_type: str = "photo",
) -> int:
    """Insert a completion record (pending approval). Returns the completion id."""
    db = await get_db()
    await db.execute(
        """INSERT OR REPLACE INTO completions
           (child_id, task_key, date, photo_file_id, media_type, approved)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (child_id, task_key, today, photo_file_id, media_type),
    )
    await db.commit()
    # Fetch the id
    rows = await db.execute_fetchall(
        "SELECT id FROM completions WHERE child_id = ? AND task_key = ? AND date = ?",
        (child_id, task_key, today),
    )
    return rows[0]["id"]


async def uncomplete_task(child_id: int, task_key: str, today: str) -> None:
    db = await get_db()
    await db.execute(
        "DELETE FROM completions WHERE child_id = ? AND task_key = ? AND date = ?",
        (child_id, task_key, today),
    )
    await db.commit()


async def is_task_completed(child_id: int, task_key: str, today: str) -> bool:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT 1 FROM completions WHERE child_id = ? AND task_key = ? AND date = ? AND approved = 1",
        (child_id, task_key, today),
    )
    return len(rows) > 0


async def is_task_pending(child_id: int, task_key: str, today: str) -> bool:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT 1 FROM completions WHERE child_id = ? AND task_key = ? AND date = ? AND approved = 0",
        (child_id, task_key, today),
    )
    return len(rows) > 0


async def get_completed_keys_for_date(child_id: int, day: str) -> set[str]:
    """Return task keys that are APPROVED for a given date."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT task_key FROM completions WHERE child_id = ? AND date = ? AND approved = 1",
        (child_id, day),
    )
    return {r["task_key"] for r in rows}


async def get_pending_keys_for_date(child_id: int, day: str) -> set[str]:
    """Return task keys that are pending approval for a given date."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT task_key FROM completions WHERE child_id = ? AND date = ? AND approved = 0",
        (child_id, day),
    )
    return {r["task_key"] for r in rows}


async def get_completed_keys_for_range(
    child_id: int, start: str, end: str
) -> dict[str, set[str]]:
    """Return {date_str: set of APPROVED task_keys} for the given range."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT task_key, date FROM completions WHERE child_id = ? AND date BETWEEN ? AND ? AND approved = 1",
        (child_id, start, end),
    )
    result: dict[str, set[str]] = {}
    for r in rows:
        result.setdefault(r["date"], set()).add(r["task_key"])
    return result


async def get_completion_by_id(completion_id: int) -> dict | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM completions WHERE id = ?", (completion_id,)
    )
    if rows:
        return dict(rows[0])
    return None


async def approve_task(completion_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE completions SET approved = 1 WHERE id = ?", (completion_id,)
    )
    await db.commit()


async def reject_task(completion_id: int) -> None:
    db = await get_db()
    await db.execute(
        "DELETE FROM completions WHERE id = ?", (completion_id,)
    )
    await db.commit()


async def get_all_families() -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM families")
    return [dict(r) for r in rows]


# ── Family password ──────────────────────────────────────


async def get_family_password(family_id: int) -> str | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT parent_password FROM families WHERE id = ?", (family_id,)
    )
    if rows and rows[0]["parent_password"]:
        return rows[0]["parent_password"]
    return None


async def set_family_password(family_id: int, password: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE families SET parent_password = ? WHERE id = ?",
        (password, family_id),
    )
    await db.commit()


# ── Extra tasks ──────────────────────────────────────────


async def add_extra_task(
    family_id: int, child_id: int, title: str, points: int, today: str
) -> int:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO extra_tasks (family_id, child_id, title, points, date) VALUES (?, ?, ?, ?, ?)",
        (family_id, child_id, title, points, today),
    )
    await db.commit()
    return cursor.lastrowid


async def get_extra_tasks_for_date(child_id: int, day: str) -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM extra_tasks WHERE child_id = ? AND date = ? ORDER BY id",
        (child_id, day),
    )
    return [dict(r) for r in rows]


async def get_extra_task(task_id: int) -> dict | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM extra_tasks WHERE id = ?", (task_id,)
    )
    if rows:
        return dict(rows[0])
    return None


async def complete_extra_task(
    task_id: int, photo_file_id: str, media_type: str = "photo"
) -> None:
    """Mark extra task as completed (pending approval)."""
    db = await get_db()
    await db.execute(
        "UPDATE extra_tasks SET completed = 1, photo_file_id = ?, media_type = ?, approved = 0 WHERE id = ?",
        (photo_file_id, media_type, task_id),
    )
    await db.commit()


async def uncomplete_extra_task(task_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE extra_tasks SET completed = 0, photo_file_id = NULL, approved = 0 WHERE id = ?",
        (task_id,),
    )
    await db.commit()


async def approve_extra_task(task_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE extra_tasks SET approved = 1 WHERE id = ?", (task_id,)
    )
    await db.commit()


async def reject_extra_task(task_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE extra_tasks SET completed = 0, photo_file_id = NULL, approved = 0 WHERE id = ?",
        (task_id,),
    )
    await db.commit()


async def get_extra_points_for_range(
    child_id: int, start: str, end: str
) -> dict[str, int]:
    """Return {date_str: total_extra_points} for APPROVED extra tasks."""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT date, SUM(points) as pts FROM extra_tasks
           WHERE child_id = ? AND date BETWEEN ? AND ? AND completed = 1 AND approved = 1
           GROUP BY date""",
        (child_id, start, end),
    )
    return {r["date"]: r["pts"] for r in rows}


async def get_extra_points_for_date(child_id: int, day: str) -> int:
    """Return total extra points for APPROVED extra tasks on a given date."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT SUM(points) as pts FROM extra_tasks WHERE child_id = ? AND date = ? AND completed = 1 AND approved = 1",
        (child_id, day),
    )
    if rows and rows[0]["pts"]:
        return rows[0]["pts"]
    return 0


# ── Child tasks (per-child checklist) ───────────────────


async def initialize_child_tasks(child_id: int) -> None:
    """Populate child_tasks with the standard 8 daily + sunday tasks."""
    db = await get_db()
    all_tasks = list(DAILY_TASKS) + [SUNDAY_TASK]
    for i, t in enumerate(all_tasks):
        await db.execute(
            """INSERT OR IGNORE INTO child_tasks
               (child_id, task_key, label, task_group, is_standard, enabled, sort_order)
               VALUES (?, ?, ?, ?, 1, 1, ?)""",
            (child_id, t.key, t.label, t.group, i),
        )
    await db.commit()


async def ensure_child_tasks_initialized(child_id: int) -> None:
    """Lazy initialization — if no rows exist yet, insert standard tasks."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT 1 FROM child_tasks WHERE child_id = ? LIMIT 1", (child_id,)
    )
    if not rows:
        await initialize_child_tasks(child_id)


async def get_child_tasks(child_id: int) -> list[dict]:
    """Return all enabled tasks for a child, ordered by sort_order."""
    await ensure_child_tasks_initialized(child_id)
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM child_tasks WHERE child_id = ? AND enabled = 1 ORDER BY sort_order",
        (child_id,),
    )
    return [dict(r) for r in rows]


async def get_child_all_tasks(child_id: int) -> list[dict]:
    """Return all tasks (including disabled) for management UI."""
    await ensure_child_tasks_initialized(child_id)
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM child_tasks WHERE child_id = ? ORDER BY sort_order",
        (child_id,),
    )
    return [dict(r) for r in rows]


async def toggle_child_task(child_id: int, task_key: str, enabled: bool) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE child_tasks SET enabled = ? WHERE child_id = ? AND task_key = ?",
        (int(enabled), child_id, task_key),
    )
    await db.commit()


async def add_custom_child_task(
    child_id: int, label: str, group: str = "custom"
) -> str:
    """Add a custom task. Returns the generated task_key."""
    await ensure_child_tasks_initialized(child_id)
    db = await get_db()
    # Generate unique key
    rows = await db.execute_fetchall(
        "SELECT MAX(sort_order) as mx FROM child_tasks WHERE child_id = ?",
        (child_id,),
    )
    next_order = (rows[0]["mx"] or 0) + 1
    task_key = f"custom_{child_id}_{next_order}"
    await db.execute(
        """INSERT INTO child_tasks
           (child_id, task_key, label, task_group, is_standard, enabled, sort_order)
           VALUES (?, ?, ?, ?, 0, 1, ?)""",
        (child_id, task_key, label, group, next_order),
    )
    await db.commit()
    return task_key


async def remove_custom_child_task(child_id: int, task_key: str) -> None:
    db = await get_db()
    await db.execute(
        "DELETE FROM child_tasks WHERE child_id = ? AND task_key = ? AND is_standard = 0",
        (child_id, task_key),
    )
    await db.commit()


async def reset_child_tasks(child_id: int) -> None:
    """Remove all tasks for child and re-initialize with standard set."""
    db = await get_db()
    await db.execute("DELETE FROM child_tasks WHERE child_id = ?", (child_id,))
    await db.commit()
    await initialize_child_tasks(child_id)


async def delete_family(family_id: int) -> list[int]:
    """Delete family and all related data. Returns telegram_ids of all members."""
    db = await get_db()
    # Get all member telegram_ids before deleting
    rows = await db.execute_fetchall(
        "SELECT telegram_id FROM users WHERE family_id = ?", (family_id,)
    )
    telegram_ids = [r["telegram_id"] for r in rows]
    # Get child user ids for child_tasks/completions cleanup
    child_rows = await db.execute_fetchall(
        "SELECT id FROM users WHERE family_id = ? AND role = 'child'", (family_id,)
    )
    child_ids = [r["id"] for r in child_rows]
    # Delete in order: completions, extra_tasks, child_tasks, users, family
    for cid in child_ids:
        await db.execute("DELETE FROM completions WHERE child_id = ?", (cid,))
        await db.execute("DELETE FROM child_tasks WHERE child_id = ?", (cid,))
    await db.execute("DELETE FROM extra_tasks WHERE family_id = ?", (family_id,))
    await db.execute("DELETE FROM users WHERE family_id = ?", (family_id,))
    await db.execute("DELETE FROM families WHERE id = ?", (family_id,))
    await db.commit()
    return telegram_ids
