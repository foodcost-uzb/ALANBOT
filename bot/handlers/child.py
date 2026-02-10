from __future__ import annotations

from datetime import date

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ..database import (
    complete_extra_task,
    complete_task,
    get_completed_keys_for_date,
    get_extra_task,
    get_extra_tasks_for_date,
    get_family_parents,
    get_user,
    uncomplete_extra_task,
    uncomplete_task,
)
from ..keyboards import checklist_kb
from ..tasks_config import ALL_TASK_KEYS, DAILY_TASKS, SUNDAY_TASK

router = Router()


class PhotoSubmit(StatesGroup):
    waiting_photo = State()


def _is_sunday(d: date | None = None) -> bool:
    return (d or date.today()).weekday() == 6


def _task_label(key: str) -> str:
    for t in DAILY_TASKS:
        if t.key == key:
            return t.label
    if key == SUNDAY_TASK.key:
        return SUNDAY_TASK.label
    return key


async def _require_child(message_or_cb) -> dict | None:
    tg_id = message_or_cb.from_user.id
    user = await get_user(tg_id)
    if not user or user["role"] != "child":
        target = (
            message_or_cb
            if isinstance(message_or_cb, Message)
            else message_or_cb.message
        )
        await target.answer("⛔ Эта команда доступна только детям.")
        return None
    return user


async def _build_checklist_kb(user_id: int, today: date):
    today_str = today.isoformat()
    completed = await get_completed_keys_for_date(user_id, today_str)
    extras = await get_extra_tasks_for_date(user_id, today_str)
    return checklist_kb(completed, is_sunday=_is_sunday(today), extra_tasks=extras)


async def send_checklist(bot: Bot, child_telegram_id: int) -> None:
    """Send today's checklist to a child. Used by scheduler and /checklist."""
    user = await get_user(child_telegram_id)
    if not user or user["role"] != "child":
        return

    today = date.today()
    kb = await _build_checklist_kb(user["id"], today)

    await bot.send_message(
        child_telegram_id,
        "📋 <b>Твой чеклист на сегодня:</b>",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.message(Command("checklist"))
async def cmd_checklist(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await _require_child(message)
    if not user:
        return
    await send_checklist(message.bot, message.from_user.id)


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery) -> None:
    await callback.answer()


# ── Regular tasks: check / done ──────────────────────────


@router.callback_query(F.data.startswith("check:"))
async def check_task_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Child taps an uncompleted task — ask for photo confirmation."""
    await callback.answer()
    user = await _require_child(callback)
    if not user:
        return

    task_key = callback.data.split(":", 1)[1]
    if task_key not in ALL_TASK_KEYS:
        await callback.answer("Неизвестная задача.", show_alert=True)
        return

    label = _task_label(task_key)
    await state.set_state(PhotoSubmit.waiting_photo)
    await state.update_data(task_key=task_key, extra_id=None)
    await callback.message.answer(
        f"📸 Отправь фото для задачи: <b>{label}</b>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("done:"))
async def done_task_cb(callback: CallbackQuery) -> None:
    """Toggle-off: unmark a completed task."""
    await callback.answer()
    user = await _require_child(callback)
    if not user:
        return

    task_key = callback.data.split(":", 1)[1]
    if task_key not in ALL_TASK_KEYS:
        await callback.answer("Неизвестная задача.", show_alert=True)
        return

    today = date.today()
    await uncomplete_task(user["id"], task_key, today.isoformat())

    kb = await _build_checklist_kb(user["id"], today)
    await callback.message.edit_reply_markup(reply_markup=kb)


# ── Extra tasks: excheck / exdone ────────────────────────


@router.callback_query(F.data.startswith("excheck:"))
async def excheck_task_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Child taps an uncompleted extra task — ask for photo."""
    await callback.answer()
    user = await _require_child(callback)
    if not user:
        return

    extra_id = int(callback.data.split(":", 1)[1])
    et = await get_extra_task(extra_id)
    if not et:
        await callback.answer("Задание не найдено.", show_alert=True)
        return

    await state.set_state(PhotoSubmit.waiting_photo)
    await state.update_data(task_key=None, extra_id=extra_id)
    await callback.message.answer(
        f"📸 Отправь фото для задачи: <b>{et['title']}</b>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("exdone:"))
async def exdone_task_cb(callback: CallbackQuery) -> None:
    """Toggle-off extra task."""
    await callback.answer()
    user = await _require_child(callback)
    if not user:
        return

    extra_id = int(callback.data.split(":", 1)[1])
    await uncomplete_extra_task(extra_id)

    today = date.today()
    kb = await _build_checklist_kb(user["id"], today)
    await callback.message.edit_reply_markup(reply_markup=kb)


# ── Photo handler (shared for regular + extra) ───────────


@router.message(PhotoSubmit.waiting_photo, F.photo)
async def receive_photo(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    data = await state.get_data()
    photo_file_id = message.photo[-1].file_id
    today = date.today()
    today_str = today.isoformat()

    task_key = data.get("task_key")
    extra_id = data.get("extra_id")

    if task_key:
        label = _task_label(task_key)
        await complete_task(user["id"], task_key, today_str, photo_file_id)
    elif extra_id:
        et = await get_extra_task(extra_id)
        label = et["title"] if et else "Доп. задание"
        await complete_extra_task(extra_id, photo_file_id)
    else:
        await state.clear()
        return

    await state.clear()
    await message.answer(f"✅ Задача «{label}» выполнена!")

    # Notify parents with photo
    parents = await get_family_parents(user["family_id"])
    for parent in parents:
        try:
            await message.bot.send_photo(
                parent["telegram_id"],
                photo=photo_file_id,
                caption=f"✅ {user['name']} выполнил(а): <b>{label}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass

    # Refresh checklist
    await send_checklist(message.bot, message.from_user.id)


@router.message(PhotoSubmit.waiting_photo)
async def waiting_photo_not_photo(message: Message) -> None:
    await message.answer("📸 Пожалуйста, отправь именно фотографию.")
