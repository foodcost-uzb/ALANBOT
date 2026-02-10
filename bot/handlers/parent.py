from __future__ import annotations

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ..database import (
    add_extra_task,
    get_completed_keys_for_date,
    get_completed_keys_for_range,
    get_extra_points_for_date,
    get_extra_points_for_range,
    get_family_children,
    get_family_invite_code,
    get_user,
    set_family_password,
)
from ..keyboards import child_picker_kb
from ..scoring import format_daily_summary, format_weekly_report
from ..tasks_config import SUNDAY_TASK

HISTORY_WEEKS = 4

router = Router()


class ExtraTask(StatesGroup):
    waiting_child = State()
    waiting_title = State()
    waiting_points = State()


class ChangePassword(StatesGroup):
    waiting_new_password = State()


# ── Helpers ───────────────────────────────────────────────


async def _require_parent(message_or_cb) -> dict | None:
    tg_id = message_or_cb.from_user.id
    user = await get_user(tg_id)
    if not user or user["role"] != "parent":
        target = (
            message_or_cb
            if isinstance(message_or_cb, Message)
            else message_or_cb.message
        )
        await target.answer("⛔ Эта команда доступна только родителям.")
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
        extra_pts = await get_extra_points_for_date(child["id"], today_str)
        text = format_daily_summary(child["name"], today, completed, is_sunday)
        if extra_pts:
            text += f"\n⭐ Доп. задания: +{extra_pts} б."
        await message.answer(text, parse_mode="HTML")


# ── /report ──────────────────────────────────────────────


@router.message(Command("report"))
async def cmd_report(message: Message) -> None:
    user = await _require_parent(message)
    if not user:
        return

    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)

    children = await get_family_children(user["family_id"])
    if not children:
        await message.answer("В семье пока нет детей.")
        return

    for child in children:
        daily_completed = await get_completed_keys_for_range(
            child["id"], start.isoformat(), end.isoformat()
        )
        for i in range(7):
            d = (start + timedelta(days=i)).isoformat()
            daily_completed.setdefault(d, set())

        sunday_str = end.isoformat()
        sunday_done = SUNDAY_TASK.key in daily_completed.get(sunday_str, set())

        extra_pts = await get_extra_points_for_range(
            child["id"], start.isoformat(), end.isoformat()
        )
        total_extra = sum(extra_pts.values())

        text = format_weekly_report(
            child["name"], start, end, daily_completed, sunday_done
        )
        if total_extra:
            text += f"\n⭐ Доп. задания за неделю: +{total_extra} б."
        await message.answer(text, parse_mode="HTML")


# ── /history ─────────────────────────────────────────────


@router.message(Command("history"))
async def cmd_history(message: Message) -> None:
    user = await _require_parent(message)
    if not user:
        return

    children = await get_family_children(user["family_id"])
    if not children:
        await message.answer("В семье пока нет детей.")
        return

    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())

    for child in children:
        parts = [f"📜 <b>История — {child['name']}</b>\n"]

        for w in range(1, HISTORY_WEEKS + 1):
            start = current_week_start - timedelta(weeks=w)
            end = start + timedelta(days=6)

            daily_completed = await get_completed_keys_for_range(
                child["id"], start.isoformat(), end.isoformat()
            )
            for i in range(7):
                d = (start + timedelta(days=i)).isoformat()
                daily_completed.setdefault(d, set())

            sunday_str = end.isoformat()
            sunday_done = SUNDAY_TASK.key in daily_completed.get(sunday_str, set())

            text = format_weekly_report(
                child["name"], start, end, daily_completed, sunday_done
            )
            parts.append(text)

        await message.answer("\n\n".join(parts), parse_mode="HTML")


# ── /extra — assign bonus task to child ──────────────────


@router.message(Command("extra"))
async def cmd_extra(message: Message, state: FSMContext) -> None:
    user = await _require_parent(message)
    if not user:
        return

    children = await get_family_children(user["family_id"])
    if not children:
        await message.answer("В семье пока нет детей.")
        return

    if len(children) == 1:
        await state.set_state(ExtraTask.waiting_title)
        await state.update_data(child_id=children[0]["id"], child_name=children[0]["name"])
        await message.answer(
            f"Доп. задание для <b>{children[0]['name']}</b>.\n"
            "Введите название задания:",
            parse_mode="HTML",
        )
    else:
        await state.set_state(ExtraTask.waiting_child)
        await message.answer(
            "Выберите ребёнка для доп. задания:",
            reply_markup=child_picker_kb(children, "extrachild"),
        )


@router.callback_query(F.data.startswith("extrachild:"))
async def extra_pick_child(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    user = await _require_parent(callback)
    if not user:
        return

    child_id = int(callback.data.split(":", 1)[1])
    children = await get_family_children(user["family_id"])
    child = next((c for c in children if c["id"] == child_id), None)
    if not child:
        await callback.message.edit_text("Ребёнок не найден.")
        return

    await state.set_state(ExtraTask.waiting_title)
    await state.update_data(child_id=child_id, child_name=child["name"])
    await callback.message.edit_text(
        f"Доп. задание для <b>{child['name']}</b>.\n"
        "Введите название задания:",
        parse_mode="HTML",
    )


@router.message(ExtraTask.waiting_title)
async def extra_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(ExtraTask.waiting_points)
    await message.answer("Сколько бонусных баллов? (число, по умолчанию 1):")


@router.message(ExtraTask.waiting_points)
async def extra_points(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if text == "":
        points = 1
    else:
        try:
            points = int(text)
            if points < 1:
                raise ValueError
        except ValueError:
            await message.answer("❌ Введите положительное число:")
            return

    user = await get_user(message.from_user.id)
    data = await state.get_data()
    today = date.today().isoformat()

    task_id = await add_extra_task(
        user["family_id"], data["child_id"], data["title"], points, today
    )
    await state.clear()

    await message.answer(
        f"⭐ Доп. задание назначено!\n"
        f"<b>{data['title']}</b> (+{points} б.) для {data['child_name']}",
        parse_mode="HTML",
    )

    # Notify child
    from ..database import get_user as _get_user_by_id
    children = await get_family_children(user["family_id"])
    child = next((c for c in children if c["id"] == data["child_id"]), None)
    if child:
        try:
            await message.bot.send_message(
                child["telegram_id"],
                f"⭐ Новое доп. задание от родителя!\n"
                f"<b>{data['title']}</b> (+{points} б.)\n\n"
                f"Нажми /checklist чтобы увидеть его в списке.",
                parse_mode="HTML",
            )
        except Exception:
            pass


# ── /password — change parent password ───────────────────


@router.message(Command("password"))
async def cmd_password(message: Message, state: FSMContext) -> None:
    user = await _require_parent(message)
    if not user:
        return
    await state.set_state(ChangePassword.waiting_new_password)
    await message.answer("🔒 Введите новый пароль для регистрации родителей:")


@router.message(ChangePassword.waiting_new_password)
async def process_new_password(message: Message, state: FSMContext) -> None:
    user = await get_user(message.from_user.id)
    new_password = message.text.strip()
    if len(new_password) < 1:
        await message.answer("❌ Пароль не может быть пустым. Попробуйте ещё раз:")
        return

    await set_family_password(user["family_id"], new_password)
    await state.clear()
    await message.answer(
        f"✅ Пароль изменён на: <b>{new_password}</b>",
        parse_mode="HTML",
    )
