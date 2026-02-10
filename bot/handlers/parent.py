from __future__ import annotations

from datetime import date, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from ..database import (
    get_completed_keys_for_date,
    get_completed_keys_for_range,
    get_family_children,
    get_family_invite_code,
    get_user,
)
from ..scoring import format_daily_summary, format_weekly_report
from ..tasks_config import SUNDAY_TASK

router = Router()


# ── Helpers ───────────────────────────────────────────────


async def _require_parent(message: Message) -> dict | None:
    user = await get_user(message.from_user.id)
    if not user or user["role"] != "parent":
        await message.answer("⛔ Эта команда доступна только родителям.")
        return None
    return user


# ── /invite ──────────────────────────────────────────────


@router.message(Command("invite"))
async def cmd_invite(message: Message) -> None:
    user = await _require_parent(message)
    if not user:
        return
    code = await get_family_invite_code(user["family_id"])
    await message.answer(
        f"Инвайт-код вашей семьи: <b>{code}</b>\n"
        "Передайте его ребёнку для привязки.",
        parse_mode="HTML",
    )


# ── /today ───────────────────────────────────────────────


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    user = await _require_parent(message)
    if not user:
        return

    children = await get_family_children(user["family_id"])
    if not children:
        await message.answer("В семье пока нет детей.")
        return

    today = date.today()
    today_str = today.isoformat()
    is_sunday = today.weekday() == 6

    for child in children:
        completed = await get_completed_keys_for_date(child["id"], today_str)
        text = format_daily_summary(child["name"], today, completed, is_sunday)
        await message.answer(text, parse_mode="HTML")


# ── /report ──────────────────────────────────────────────


@router.message(Command("report"))
async def cmd_report(message: Message) -> None:
    user = await _require_parent(message)
    if not user:
        return

    today = date.today()
    start = today - timedelta(days=today.weekday())  # Monday
    end = start + timedelta(days=6)  # Sunday

    children = await get_family_children(user["family_id"])
    if not children:
        await message.answer("В семье пока нет детей.")
        return

    for child in children:
        daily_completed = await get_completed_keys_for_range(
            child["id"], start.isoformat(), end.isoformat()
        )
        # Fill in missing days with empty sets
        for i in range(7):
            d = (start + timedelta(days=i)).isoformat()
            daily_completed.setdefault(d, set())

        sunday_str = end.isoformat()
        sunday_done = SUNDAY_TASK.key in daily_completed.get(sunday_str, set())

        text = format_weekly_report(
            child["name"], start, end, daily_completed, sunday_done
        )
        await message.answer(text, parse_mode="HTML")
