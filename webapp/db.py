"""Standalone DB connection for the web app (WAL mode, separate from bot)."""

from __future__ import annotations

import aiosqlite

from bot.config import DB_PATH

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


# ── User queries ────────────────────────────────────────


async def get_user_by_telegram_id(telegram_id: int) -> dict | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
    )
    return dict(rows[0]) if rows else None


async def get_user_by_id(user_id: int) -> dict | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    )
    return dict(rows[0]) if rows else None


# ── Family queries ──────────────────────────────────────


async def get_family_children(family_id: int) -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM users WHERE family_id = ? AND role = 'child'", (family_id,)
    )
    return [dict(r) for r in rows]


async def get_family_parents(family_id: int) -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM users WHERE family_id = ? AND role = 'parent'", (family_id,)
    )
    return [dict(r) for r in rows]


async def get_family_invite_code(family_id: int) -> str | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT invite_code FROM families WHERE id = ?", (family_id,)
    )
    return rows[0]["invite_code"] if rows else None


# ── Completions ─────────────────────────────────────────


async def get_completed_keys_for_date(child_id: int, day: str) -> set[str]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT task_key FROM completions WHERE child_id = ? AND date = ? AND approved = 1",
        (child_id, day),
    )
    return {r["task_key"] for r in rows}


async def get_pending_keys_for_date(child_id: int, day: str) -> set[str]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT task_key FROM completions WHERE child_id = ? AND date = ? AND approved = 0",
        (child_id, day),
    )
    return {r["task_key"] for r in rows}


async def get_completed_keys_for_range(
    child_id: int, start: str, end: str
) -> dict[str, set[str]]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT task_key, date FROM completions WHERE child_id = ? AND date BETWEEN ? AND ? AND approved = 1",
        (child_id, start, end),
    )
    result: dict[str, set[str]] = {}
    for r in rows:
        result.setdefault(r["date"], set()).add(r["task_key"])
    return result


async def complete_task(
    child_id: int, task_key: str, today: str, photo_file_id: str | None = None, media_type: str = "photo"
) -> int:
    db = await get_db()
    await db.execute(
        """INSERT OR REPLACE INTO completions
           (child_id, task_key, date, photo_file_id, media_type, approved)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (child_id, task_key, today, photo_file_id, media_type),
    )
    await db.commit()
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


async def get_completion_by_id(completion_id: int) -> dict | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM completions WHERE id = ?", (completion_id,)
    )
    return dict(rows[0]) if rows else None


async def approve_completion(completion_id: int) -> None:
    db = await get_db()
    await db.execute("UPDATE completions SET approved = 1 WHERE id = ?", (completion_id,))
    await db.commit()


async def reject_completion(completion_id: int) -> None:
    db = await get_db()
    await db.execute("DELETE FROM completions WHERE id = ?", (completion_id,))
    await db.commit()


# ── Extra tasks ─────────────────────────────────────────


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
    return dict(rows[0]) if rows else None


async def complete_extra_task(task_id: int, photo_file_id: str, media_type: str = "photo") -> None:
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
    await db.execute("UPDATE extra_tasks SET approved = 1 WHERE id = ?", (task_id,))
    await db.commit()


async def reject_extra_task(task_id: int) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE extra_tasks SET completed = 0, photo_file_id = NULL, approved = 0 WHERE id = ?",
        (task_id,),
    )
    await db.commit()


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


async def get_extra_points_for_date(child_id: int, day: str) -> int:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT SUM(points) as pts FROM extra_tasks WHERE child_id = ? AND date = ? AND completed = 1 AND approved = 1",
        (child_id, day),
    )
    return rows[0]["pts"] or 0 if rows and rows[0]["pts"] else 0


async def get_extra_points_for_range(
    child_id: int, start: str, end: str
) -> dict[str, int]:
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT date, SUM(points) as pts FROM extra_tasks
           WHERE child_id = ? AND date BETWEEN ? AND ? AND completed = 1 AND approved = 1
           GROUP BY date""",
        (child_id, start, end),
    )
    return {r["date"]: r["pts"] for r in rows}


# ── Pending approvals ───────────────────────────────────


async def get_pending_approvals(family_id: int) -> list[dict]:
    """Get all pending completions and extra tasks for a family."""
    db = await get_db()
    # Pending regular completions
    rows = await db.execute_fetchall(
        """SELECT c.id, c.child_id, c.task_key, c.date, c.photo_file_id, c.media_type,
                  u.name as child_name, 'task' as type
           FROM completions c
           JOIN users u ON u.id = c.child_id
           WHERE u.family_id = ? AND c.approved = 0
           ORDER BY c.completed_at DESC""",
        (family_id,),
    )
    results = [dict(r) for r in rows]
    # Pending extra tasks
    rows2 = await db.execute_fetchall(
        """SELECT e.id, e.child_id, e.title, e.points, e.date, e.photo_file_id, e.media_type,
                  u.name as child_name, 'extra' as type
           FROM extra_tasks e
           JOIN users u ON u.id = e.child_id
           WHERE e.family_id = ? AND e.completed = 1 AND e.approved = 0
           ORDER BY e.id DESC""",
        (family_id,),
    )
    results.extend(dict(r) for r in rows2)
    return results


# ── Child tasks (per-child checklist) ───────────────────


async def ensure_child_tasks_initialized(child_id: int) -> None:
    from bot.tasks_config import DAILY_TASKS, SUNDAY_TASK
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT 1 FROM child_tasks WHERE child_id = ? LIMIT 1", (child_id,)
    )
    if not rows:
        all_tasks = list(DAILY_TASKS) + [SUNDAY_TASK]
        for i, t in enumerate(all_tasks):
            await db.execute(
                """INSERT OR IGNORE INTO child_tasks
                   (child_id, task_key, label, task_group, is_standard, enabled, sort_order)
                   VALUES (?, ?, ?, ?, 1, 1, ?)""",
                (child_id, t.key, t.label, t.group, i),
            )
        await db.commit()


async def get_child_enabled_tasks(child_id: int) -> list[dict]:
    await ensure_child_tasks_initialized(child_id)
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM child_tasks WHERE child_id = ? AND enabled = 1 ORDER BY sort_order",
        (child_id,),
    )
    return [dict(r) for r in rows]


async def get_child_all_tasks(child_id: int) -> list[dict]:
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


async def add_custom_child_task(child_id: int, label: str, group: str = "custom") -> str:
    await ensure_child_tasks_initialized(child_id)
    db = await get_db()
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
    db = await get_db()
    await db.execute("DELETE FROM child_tasks WHERE child_id = ?", (child_id,))
    await db.commit()
    await ensure_child_tasks_initialized(child_id)


async def delete_family(family_id: int) -> list[int]:
    """Delete family and all related data. Returns telegram_ids of all members."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT telegram_id FROM users WHERE family_id = ?", (family_id,)
    )
    telegram_ids = [r["telegram_id"] for r in rows]
    child_rows = await db.execute_fetchall(
        "SELECT id FROM users WHERE family_id = ? AND role = 'child'", (family_id,)
    )
    child_ids = [r["id"] for r in child_rows]
    for cid in child_ids:
        await db.execute("DELETE FROM completions WHERE child_id = ?", (cid,))
        await db.execute("DELETE FROM child_tasks WHERE child_id = ?", (cid,))
    await db.execute("DELETE FROM extra_tasks WHERE family_id = ?", (family_id,))
    await db.execute("DELETE FROM users WHERE family_id = ?", (family_id,))
    await db.execute("DELETE FROM families WHERE id = ?", (family_id,))
    await db.commit()
    return telegram_ids
