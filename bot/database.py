from __future__ import annotations

import random
import string
from datetime import date, datetime, timedelta

import aiosqlite

from .config import DB_PATH

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
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
            photo_file_id TEXT
        );

        CREATE TABLE IF NOT EXISTS completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            child_id INTEGER NOT NULL REFERENCES users(id),
            task_key TEXT NOT NULL,
            date TEXT NOT NULL,
            photo_file_id TEXT,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(child_id, task_key, date)
        );
        """
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


# ── Completions ───────────────────────────────────────────


async def complete_task(
    child_id: int, task_key: str, today: str, photo_file_id: str | None = None
) -> None:
    db = await get_db()
    await db.execute(
        "INSERT OR IGNORE INTO completions (child_id, task_key, date, photo_file_id) VALUES (?, ?, ?, ?)",
        (child_id, task_key, today, photo_file_id),
    )
    await db.commit()


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
        "SELECT 1 FROM completions WHERE child_id = ? AND task_key = ? AND date = ?",
        (child_id, task_key, today),
    )
    return len(rows) > 0


async def get_completed_keys_for_date(child_id: int, day: str) -> set[str]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT task_key FROM completions WHERE child_id = ? AND date = ?",
        (child_id, day),
    )
    return {r["task_key"] for r in rows}


async def get_completed_keys_for_range(
    child_id: int, start: str, end: str
) -> dict[str, set[str]]:
    """Return {date_str: set of completed task_keys} for the given range."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT task_key, date FROM completions WHERE child_id = ? AND date BETWEEN ? AND ?",
        (child_id, start, end),
    )
    result: dict[str, set[str]] = {}
    for r in rows:
        result.setdefault(r["date"], set()).add(r["task_key"])
    return result


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


async def complete_extra_task(task_id: int, photo_file_id: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE extra_tasks SET completed = 1, photo_file_id = ? WHERE id = ?",
        (photo_file_id, task_id),
    )
    await db.commit()


async def uncomplete_extra_task(task_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE extra_tasks SET completed = 0, photo_file_id = NULL WHERE id = ?",
        (task_id,),
    )
    await db.commit()


async def get_extra_points_for_range(
    child_id: int, start: str, end: str
) -> dict[str, int]:
    """Return {date_str: total_extra_points} for completed extra tasks."""
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT date, SUM(points) as pts FROM extra_tasks
           WHERE child_id = ? AND date BETWEEN ? AND ? AND completed = 1
           GROUP BY date""",
        (child_id, start, end),
    )
    return {r["date"]: r["pts"] for r in rows}


async def get_extra_points_for_date(child_id: int, day: str) -> int:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT SUM(points) as pts FROM extra_tasks WHERE child_id = ? AND date = ? AND completed = 1",
        (child_id, day),
    )
    if rows and rows[0]["pts"]:
        return rows[0]["pts"]
    return 0
