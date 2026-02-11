from __future__ import annotations

from datetime import date

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ..child_tasks import get_active_tasks_for_child, get_child_all_task_keys, get_task_label
from ..database import (
    complete_extra_task,
    complete_task,
    get_completed_keys_for_date,
    get_extra_task,
    get_extra_tasks_for_date,
    get_family_parents,
    get_pending_keys_for_date,
    get_user,
    uncomplete_extra_task,
    uncomplete_task,
)
from ..keyboards import approval_kb, checklist_kb

router = Router()


class PhotoSubmit(StatesGroup):
    waiting_photo = State()


def _is_sunday(d: date | None = None) -> bool:
    return (d or date.today()).weekday() == 6


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
    is_sunday = _is_sunday(today)
    completed = await get_completed_keys_for_date(user_id, today_str)
    pending = await get_pending_keys_for_date(user_id, today_str)
    extras = await get_extra_tasks_for_date(user_id, today_str)
    child_tasks = await get_active_tasks_for_child(user_id, is_sunday)
    return checklist_kb(
        completed,
        pending_keys=pending,
        is_sunday=is_sunday,
        extra_tasks=extras,
        daily_tasks=child_tasks,
    )


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


# ── Pending task click ───────────────────────────────────


@router.callback_query(F.data.startswith("pending:"))
async def pending_task_cb(callback: CallbackQuery) -> None:
    """Child taps a pending task — just show a notice."""
    await callback.answer("🕐 Ожидает проверки родителем", show_alert=True)


@router.callback_query(F.data.startswith("expending:"))
async def expending_task_cb(callback: CallbackQuery) -> None:
    """Child taps a pending extra task — just show a notice."""
    await callback.answer("🕐 Ожидает проверки родителем", show_alert=True)


# ── Regular tasks: check / done ──────────────────────────


@router.callback_query(F.data.startswith("check:"))
async def check_task_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Child taps an uncompleted task — ask for photo/video confirmation."""
    await callback.answer()
    user = await _require_child(callback)
    if not user:
        return

    task_key = callback.data.split(":", 1)[1]
    valid_keys = await get_child_all_task_keys(user["id"])
    if task_key not in valid_keys:
        await callback.answer("Неизвестная задача.", show_alert=True)
        return

    label = await get_task_label(user["id"], task_key)
    await state.set_state(PhotoSubmit.waiting_photo)
    await state.update_data(task_key=task_key, extra_id=None)
    await callback.message.answer(
        f"📸 Отправь фото или видео для задачи: <b>{label}</b>",
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
    valid_keys = await get_child_all_task_keys(user["id"])
    if task_key not in valid_keys:
        await callback.answer("Неизвестная задача.", show_alert=True)
        return

    today = date.today()
    await uncomplete_task(user["id"], task_key, today.isoformat())

    kb = await _build_checklist_kb(user["id"], today)
    await callback.message.edit_reply_markup(reply_markup=kb)


# ── Extra tasks: excheck / exdone ────────────────────────


@router.callback_query(F.data.startswith("excheck:"))
async def excheck_task_cb(callback: CallbackQuery, state: FSMContext) -> None:
    """Child taps an uncompleted extra task — ask for photo/video."""
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
        f"📸 Отправь фото или видео для задачи: <b>{et['title']}</b>",
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


# ── Photo/Video handler (shared for regular + extra) ─────


@router.message(PhotoSubmit.waiting_photo, F.photo | F.video)
async def receive_media(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    data = await state.get_data()
    today = date.today()
    today_str = today.isoformat()

    # Determine media type and file_id
    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
    else:
        file_id = message.video.file_id
        media_type = "video"

    task_key = data.get("task_key")
    extra_id = data.get("extra_id")

    if task_key:
        label = await get_task_label(user["id"], task_key)
        completion_id = await complete_task(
            user["id"], task_key, today_str, file_id, media_type
        )
        is_extra = False
    elif extra_id:
        et = await get_extra_task(extra_id)
        label = et["title"] if et else "Доп. задание"
        await complete_extra_task(extra_id, file_id, media_type)
        completion_id = extra_id
        is_extra = True
    else:
        await state.clear()
        return

    await state.clear()
    await message.answer(f"🕐 Задача «{label}» отправлена на проверку родителю!")

    # Notify parents with media + approval buttons
    parents = await get_family_parents(user["family_id"])
    kb = approval_kb(completion_id, is_extra=is_extra)
    for parent in parents:
        try:
            if media_type == "video":
                await message.bot.send_video(
                    parent["telegram_id"],
                    video=file_id,
                    caption=f"🕐 {user['name']} выполнил(а): <b>{label}</b>\nОжидает одобрения",
                    parse_mode="HTML",
                    reply_markup=kb,
                )
            else:
                await message.bot.send_photo(
                    parent["telegram_id"],
                    photo=file_id,
                    caption=f"🕐 {user['name']} выполнил(а): <b>{label}</b>\nОжидает одобрения",
                    parse_mode="HTML",
                    reply_markup=kb,
                )
        except Exception:
            pass

    # Refresh checklist
    await send_checklist(message.bot, message.from_user.id)


@router.message(PhotoSubmit.waiting_photo)
async def waiting_photo_not_photo(message: Message) -> None:
    await message.answer("📸 Пожалуйста, отправь фото или видео.")
