from __future__ import annotations

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ..child_tasks import (
    child_has_shower,
    child_has_sunday_task,
    get_active_daily_tasks,
    get_task_label,
)
from ..database import (
    add_custom_child_task,
    add_extra_task,
    approve_extra_task,
    approve_task,
    delete_family,
    get_child_all_tasks,
    get_completed_keys_for_date,
    get_completed_keys_for_range,
    get_completion_by_id,
    get_extra_points_for_date,
    get_extra_points_for_range,
    get_extra_task,
    get_family_children,
    get_family_invite_code,
    get_user,
    get_user_by_id,
    reject_extra_task,
    reject_task,
    remove_custom_child_task,
    reset_child_tasks,
    set_family_password,
    toggle_child_task,
)
from ..keyboards import child_picker_kb, task_manager_kb
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


class ManageTasks(StatesGroup):
    waiting_child = State()
    viewing = State()
    waiting_new_task_label = State()


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


async def _task_label_for_child(child_id: int, key: str) -> str:
    """Get task label, falling back to child_tasks DB."""
    return await get_task_label(child_id, key)


# ── /family ──────────────────────────────────────────────


@router.message(Command("family"))
async def cmd_family(message: Message) -> None:
    user = await _require_parent(message)
    if not user:
        return

    from ..database import get_family_parents

    parents = await get_family_parents(user["family_id"])
    children = await get_family_children(user["family_id"])
    code = await get_family_invite_code(user["family_id"])

    lines = ["👨‍👩‍👧 <b>Ваша семья</b>\n"]

    lines.append("👫 <b>Родители:</b>")
    for p in parents:
        lines.append(f"  • {p['name']}")

    if children:
        lines.append("\n🧒 <b>Дети:</b>")
        for c in children:
            lines.append(f"  • {c['name']}")
    else:
        lines.append("\n🧒 Дети: пока нет")

    lines.append(f"\n🔗 Инвайт-код: <b>{code}</b>")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ── /invite ──────────────────────────────────────────────


@router.message(Command("invite"))
async def cmd_invite(message: Message) -> None:
    user = await _require_parent(message)
    if not user:
        return
    code = await get_family_invite_code(user["family_id"])
    await message.answer(
        f"Инвайт-код вашей семьи: <b>{code}</b>\n"
        "Передайте его ребёнку или второму родителю для привязки.",
        parse_mode="HTML",
    )


# ── /children — view children with today's progress ─────


@router.message(Command("children"))
async def cmd_children(message: Message) -> None:
    user = await _require_parent(message)
    if not user:
        return

    children = await get_family_children(user["family_id"])
    if not children:
        await message.answer("В семье пока нет детей.")
        return

    today_str = date.today().isoformat()
    lines = ["👨‍👩‍👧‍👦 <b>Дети:</b>\n"]

    for child in children:
        completed = await get_completed_keys_for_date(child["id"], today_str)
        daily_tasks = await get_active_daily_tasks(child["id"])
        total = len(daily_tasks)
        done = sum(1 for t in daily_tasks if t.key in completed)
        check = " ✅" if done == total else ""
        lines.append(f"  {child['name']}: {done}/{total} задач{check}")

    await message.answer("\n".join(lines), parse_mode="HTML")


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
        daily_tasks = await get_active_daily_tasks(child["id"])
        shower_req = await child_has_shower(child["id"])
        has_sunday = await child_has_sunday_task(child["id"])
        sunday_task = SUNDAY_TASK if has_sunday else None

        text = format_daily_summary(
            child["name"],
            today,
            completed,
            is_sunday and has_sunday,
            daily_tasks=daily_tasks,
            sunday_task=sunday_task or SUNDAY_TASK,
            shower_required=shower_req,
        )
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
        has_sunday = await child_has_sunday_task(child["id"])
        sunday_done = has_sunday and SUNDAY_TASK.key in daily_completed.get(sunday_str, set())

        extra_pts = await get_extra_points_for_range(
            child["id"], start.isoformat(), end.isoformat()
        )
        total_extra = sum(extra_pts.values())

        daily_tasks = await get_active_daily_tasks(child["id"])
        shower_req = await child_has_shower(child["id"])

        text = format_weekly_report(
            child["name"], start, end, daily_completed, sunday_done,
            daily_tasks=daily_tasks,
            shower_required=shower_req,
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
        daily_tasks = await get_active_daily_tasks(child["id"])
        shower_req = await child_has_shower(child["id"])
        has_sunday = await child_has_sunday_task(child["id"])

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
            sunday_done = has_sunday and SUNDAY_TASK.key in daily_completed.get(sunday_str, set())

            text = format_weekly_report(
                child["name"], start, end, daily_completed, sunday_done,
                daily_tasks=daily_tasks,
                shower_required=shower_req,
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


# ── /tasks — manage child's checklist ───────────────────


@router.message(Command("tasks"))
async def cmd_tasks(message: Message, state: FSMContext) -> None:
    user = await _require_parent(message)
    if not user:
        return

    children = await get_family_children(user["family_id"])
    if not children:
        await message.answer("В семье пока нет детей.")
        return

    if len(children) == 1:
        child = children[0]
        await _show_task_manager(message, state, child["id"], child["name"])
    else:
        await state.set_state(ManageTasks.waiting_child)
        await message.answer(
            "Выберите ребёнка для настройки чеклиста:",
            reply_markup=child_picker_kb(children, "tmchild"),
        )


@router.callback_query(F.data.startswith("tmchild:"))
async def tasks_pick_child(callback: CallbackQuery, state: FSMContext) -> None:
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

    await _show_task_manager(callback.message, state, child["id"], child["name"], edit=True)


async def _show_task_manager(
    message: Message, state: FSMContext, child_id: int, child_name: str, edit: bool = False
) -> None:
    tasks = await get_child_all_tasks(child_id)
    kb = task_manager_kb(child_id, tasks)
    await state.set_state(ManageTasks.viewing)
    await state.update_data(manage_child_id=child_id, manage_child_name=child_name)

    text = f"📝 <b>Задачи — {child_name}</b>\nНажмите для вкл/выкл:"
    if edit:
        await message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("tmtoggle:"))
async def tm_toggle(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    user = await _require_parent(callback)
    if not user:
        return

    parts = callback.data.split(":", 2)
    child_id = int(parts[1])
    task_key = parts[2]

    tasks = await get_child_all_tasks(child_id)
    current = next((t for t in tasks if t["task_key"] == task_key), None)
    if not current:
        await callback.answer("Задача не найдена.", show_alert=True)
        return

    new_enabled = not current["enabled"]
    await toggle_child_task(child_id, task_key, new_enabled)

    # Refresh
    data = await state.get_data()
    child_name = data.get("manage_child_name", "Ребёнок")
    tasks = await get_child_all_tasks(child_id)
    kb = task_manager_kb(child_id, tasks)
    await callback.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(F.data.startswith("tmdelete:"))
async def tm_delete(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    user = await _require_parent(callback)
    if not user:
        return

    parts = callback.data.split(":", 2)
    child_id = int(parts[1])
    task_key = parts[2]

    await remove_custom_child_task(child_id, task_key)

    tasks = await get_child_all_tasks(child_id)
    kb = task_manager_kb(child_id, tasks)
    await callback.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(F.data.startswith("tmadd:"))
async def tm_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    user = await _require_parent(callback)
    if not user:
        return

    child_id = int(callback.data.split(":", 1)[1])
    await state.set_state(ManageTasks.waiting_new_task_label)
    await state.update_data(manage_child_id=child_id)
    await callback.message.answer("Введите название новой задачи:")


@router.message(ManageTasks.waiting_new_task_label)
async def tm_add_label(message: Message, state: FSMContext) -> None:
    label = message.text.strip()
    if not label:
        await message.answer("❌ Название не может быть пустым. Попробуйте ещё раз:")
        return

    data = await state.get_data()
    child_id = data["manage_child_id"]
    child_name = data.get("manage_child_name", "Ребёнок")

    await add_custom_child_task(child_id, label)
    await state.set_state(ManageTasks.viewing)

    tasks = await get_child_all_tasks(child_id)
    kb = task_manager_kb(child_id, tasks)
    await message.answer(
        f"✅ Задача «{label}» добавлена!\n\n"
        f"📝 <b>Задачи — {child_name}</b>\nНажмите для вкл/выкл:",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("tmreset:"))
async def tm_reset(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("Задачи сброшены к стандартным", show_alert=True)
    user = await _require_parent(callback)
    if not user:
        return

    child_id = int(callback.data.split(":", 1)[1])
    await reset_child_tasks(child_id)

    tasks = await get_child_all_tasks(child_id)
    kb = task_manager_kb(child_id, tasks)
    await callback.message.edit_reply_markup(reply_markup=kb)


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


# ── /reset_family — delete family and all data ──────────


@router.message(Command("reset_family"))
async def cmd_reset_family(message: Message) -> None:
    user = await _require_parent(message)
    if not user:
        return

    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚠️ Да, удалить всё",
                    callback_data="reset_family_confirm",
                ),
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data="reset_family_cancel",
                ),
            ]
        ]
    )
    await message.answer(
        "⚠️ <b>Вы уверены?</b>\n\n"
        "Это удалит:\n"
        "• Всех пользователей семьи (родителей и детей)\n"
        "• Все выполненные задачи и чеклисты\n"
        "• Все доп. задания\n"
        "• Настройки задач\n\n"
        "После этого все должны будут заново пройти /start.",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "reset_family_confirm")
async def reset_family_confirm(callback: CallbackQuery) -> None:
    await callback.answer()
    user = await _require_parent(callback)
    if not user:
        return

    family_id = user["family_id"]
    telegram_ids = await delete_family(family_id)

    await callback.message.edit_text(
        "✅ Семья полностью удалена.\n"
        "Все участники могут заново зарегистрироваться через /start."
    )

    # Notify other family members
    for tg_id in telegram_ids:
        if tg_id != callback.from_user.id:
            try:
                await callback.bot.send_message(
                    tg_id,
                    "ℹ️ Семья была сброшена родителем.\n"
                    "Для повторной регистрации нажмите /start.",
                )
            except Exception:
                pass


@router.callback_query(F.data == "reset_family_cancel")
async def reset_family_cancel(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text("Отменено. Данные не удалены.")


# ── Approve / Reject regular tasks ──────────────────────


@router.callback_query(F.data.startswith("approve_task:"))
async def approve_task_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    user = await _require_parent(callback)
    if not user:
        return

    completion_id = int(callback.data.split(":", 1)[1])
    completion = await get_completion_by_id(completion_id)
    if not completion:
        await callback.message.edit_caption(
            caption="❌ Задача не найдена (возможно, уже обработана).",
        )
        return

    if completion["approved"]:
        await callback.answer("Уже одобрено.", show_alert=True)
        return

    await approve_task(completion_id)

    label = await _task_label_for_child(completion["child_id"], completion["task_key"])
    child = await get_user_by_id(completion["child_id"])
    child_name = child["name"] if child else "Ребёнок"

    await callback.message.edit_caption(
        caption=f"✅ Одобрено: {child_name} — <b>{label}</b>",
        parse_mode="HTML",
    )

    # Notify child
    if child:
        try:
            await callback.bot.send_message(
                child["telegram_id"],
                f"✅ Задача «{label}» одобрена родителем!",
            )
            # Refresh child's checklist
            from .child import send_checklist
            await send_checklist(callback.bot, child["telegram_id"])
        except Exception:
            pass


@router.callback_query(F.data.startswith("reject_task:"))
async def reject_task_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    user = await _require_parent(callback)
    if not user:
        return

    completion_id = int(callback.data.split(":", 1)[1])
    completion = await get_completion_by_id(completion_id)
    if not completion:
        await callback.message.edit_caption(
            caption="❌ Задача не найдена (возможно, уже обработана).",
        )
        return

    label = await _task_label_for_child(completion["child_id"], completion["task_key"])
    child = await get_user_by_id(completion["child_id"])
    child_name = child["name"] if child else "Ребёнок"

    await reject_task(completion_id)

    await callback.message.edit_caption(
        caption=f"❌ Отклонено: {child_name} — <b>{label}</b>",
        parse_mode="HTML",
    )

    # Notify child
    if child:
        try:
            await callback.bot.send_message(
                child["telegram_id"],
                f"❌ Задача «{label}» отклонена. Попробуй выполнить снова!",
            )
            from .child import send_checklist
            await send_checklist(callback.bot, child["telegram_id"])
        except Exception:
            pass


# ── Approve / Reject extra tasks ─────────────────────────


@router.callback_query(F.data.startswith("approve_extra:"))
async def approve_extra_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    user = await _require_parent(callback)
    if not user:
        return

    extra_id = int(callback.data.split(":", 1)[1])
    et = await get_extra_task(extra_id)
    if not et:
        await callback.message.edit_caption(
            caption="❌ Задание не найдено (возможно, уже обработано).",
        )
        return

    if et.get("approved"):
        await callback.answer("Уже одобрено.", show_alert=True)
        return

    await approve_extra_task(extra_id)

    child = await get_user_by_id(et["child_id"])
    child_name = child["name"] if child else "Ребёнок"

    await callback.message.edit_caption(
        caption=f"✅ Одобрено: {child_name} — <b>{et['title']}</b> (+{et['points']} б.)",
        parse_mode="HTML",
    )

    if child:
        try:
            await callback.bot.send_message(
                child["telegram_id"],
                f"✅ Доп. задание «{et['title']}» одобрено родителем! (+{et['points']} б.)",
            )
            from .child import send_checklist
            await send_checklist(callback.bot, child["telegram_id"])
        except Exception:
            pass


@router.callback_query(F.data.startswith("reject_extra:"))
async def reject_extra_cb(callback: CallbackQuery) -> None:
    await callback.answer()
    user = await _require_parent(callback)
    if not user:
        return

    extra_id = int(callback.data.split(":", 1)[1])
    et = await get_extra_task(extra_id)
    if not et:
        await callback.message.edit_caption(
            caption="❌ Задание не найдено (возможно, уже обработано).",
        )
        return

    child = await get_user_by_id(et["child_id"])
    child_name = child["name"] if child else "Ребёнок"

    await reject_extra_task(extra_id)

    await callback.message.edit_caption(
        caption=f"❌ Отклонено: {child_name} — <b>{et['title']}</b>",
        parse_mode="HTML",
    )

    if child:
        try:
            await callback.bot.send_message(
                child["telegram_id"],
                f"❌ Доп. задание «{et['title']}» отклонено. Попробуй выполнить снова!",
            )
            from .child import send_checklist
            await send_checklist(callback.bot, child["telegram_id"])
        except Exception:
            pass
