from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ..database import create_family, create_user, get_family_by_invite, get_user
from ..keyboards import role_selection_kb

router = Router()


class Registration(StatesGroup):
    waiting_invite_code = State()
    waiting_name = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await get_user(message.from_user.id)
    if user:
        role_text = "родитель" if user["role"] == "parent" else "ребёнок"
        await message.answer(
            f"Вы уже зарегистрированы как {role_text}.\n"
            "Используйте /today (родитель) или /checklist (ребёнок)."
        )
        return
    await message.answer(
        "Привет! Я бот для ежедневного чеклиста.\nКто вы?",
        reply_markup=role_selection_kb(),
    )


@router.callback_query(F.data == "role:parent")
async def role_parent(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    user = await get_user(callback.from_user.id)
    if user:
        await callback.message.edit_text("Вы уже зарегистрированы.")
        return

    family_id, invite_code = await create_family()
    name = callback.from_user.full_name or "Родитель"
    await create_user(callback.from_user.id, "parent", family_id, name)

    await callback.message.edit_text(
        f"✅ Вы зарегистрированы как родитель!\n\n"
        f"Инвайт-код для ребёнка: <b>{invite_code}</b>\n"
        f"Отправьте этот код ребёнку, чтобы он привязался к вашей семье.\n\n"
        f"Команды:\n"
        f"/today — прогресс ребёнка за сегодня\n"
        f"/invite — показать инвайт-код\n"
        f"/report — недельный отчёт",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "role:child")
async def role_child(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    user = await get_user(callback.from_user.id)
    if user:
        await callback.message.edit_text("Вы уже зарегистрированы.")
        return

    await state.set_state(Registration.waiting_invite_code)
    await callback.message.edit_text(
        "Введите инвайт-код, который дал вам родитель:"
    )


@router.message(Registration.waiting_invite_code)
async def process_invite_code(message: Message, state: FSMContext) -> None:
    code = message.text.strip()
    family = await get_family_by_invite(code)
    if not family:
        await message.answer("❌ Неверный код. Попробуйте ещё раз:")
        return

    await state.update_data(family_id=family["id"])
    await state.set_state(Registration.waiting_name)
    await message.answer("Как тебя зовут?")


@router.message(Registration.waiting_name)
async def process_child_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    data = await state.get_data()
    family_id = data["family_id"]

    await create_user(message.from_user.id, "child", family_id, name)
    await state.clear()
    await message.answer(
        f"✅ {name}, ты привязан к семье!\n\n"
        f"Каждое утро я буду присылать тебе чеклист.\n"
        f"Команда /checklist — посмотреть задачи на сегодня."
    )
