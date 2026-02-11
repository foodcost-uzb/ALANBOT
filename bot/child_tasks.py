"""Centralized helpers for per-child task lists."""

from __future__ import annotations

from .database import ensure_child_tasks_initialized, get_child_tasks
from .tasks_config import SHOWER_KEY, SUNDAY_TASK, TaskDef


async def get_active_tasks_for_child(
    child_id: int, is_sunday: bool
) -> tuple[TaskDef, ...]:
    """Return enabled TaskDefs for a child (daily + sunday if applicable)."""
    rows = await get_child_tasks(child_id)
    tasks: list[TaskDef] = []
    for r in rows:
        if r["task_group"] == "sunday" and not is_sunday:
            continue
        tasks.append(TaskDef(key=r["task_key"], label=r["label"], group=r["task_group"]))
    return tuple(tasks)


async def get_active_daily_tasks(child_id: int) -> tuple[TaskDef, ...]:
    """Return enabled daily tasks only (no sunday)."""
    rows = await get_child_tasks(child_id)
    return tuple(
        TaskDef(key=r["task_key"], label=r["label"], group=r["task_group"])
        for r in rows
        if r["task_group"] != "sunday"
    )


async def get_child_all_task_keys(child_id: int) -> set[str]:
    """Return all enabled task keys (including sunday) for validation."""
    rows = await get_child_tasks(child_id)
    return {r["task_key"] for r in rows}


async def child_has_shower(child_id: int) -> bool:
    """Check if the child has the shower task enabled."""
    keys = await get_child_all_task_keys(child_id)
    return SHOWER_KEY in keys


async def child_has_sunday_task(child_id: int) -> bool:
    """Check if the child has the sunday room_clean task enabled."""
    rows = await get_child_tasks(child_id)
    return any(r["task_key"] == SUNDAY_TASK.key for r in rows)


async def get_task_label(child_id: int, task_key: str) -> str:
    """Get the label for a task_key from the child's task list."""
    await ensure_child_tasks_initialized(child_id)
    rows = await get_child_tasks(child_id)
    for r in rows:
        if r["task_key"] == task_key:
            return r["label"]
    return task_key
