from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .tasks_config import DAILY_TASKS, GROUP_HEADERS, SUNDAY_TASK


# ── Start / Role selection ────────────────────────────────


def role_selection_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👨‍👩‍👧 Я родитель", callback_data="role:parent"
                ),
                InlineKeyboardButton(
                    text="🧒 Я ребёнок", callback_data="role:child"
                ),
            ]
        ]
    )


# ── Child: checklist ──────────────────────────────────────


def checklist_kb(
    completed_keys: set[str], is_sunday: bool = False
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []

    current_group = None
    for t in DAILY_TASKS:
        if t.group != current_group:
            current_group = t.group
            buttons.append(
                [InlineKeyboardButton(
                    text=GROUP_HEADERS[current_group],
                    callback_data="noop",
                )]
            )
        done = t.key in completed_keys
        icon = "✅" if done else "⬜"
        cb = f"done:{t.key}" if done else f"check:{t.key}"
        buttons.append(
            [InlineKeyboardButton(text=f"{icon} {t.label}", callback_data=cb)]
        )

    if is_sunday:
        buttons.append(
            [InlineKeyboardButton(
                text=GROUP_HEADERS["sunday"],
                callback_data="noop",
            )]
        )
        done = SUNDAY_TASK.key in completed_keys
        icon = "✅" if done else "⬜"
        cb = f"done:{SUNDAY_TASK.key}" if done else f"check:{SUNDAY_TASK.key}"
        buttons.append(
            [InlineKeyboardButton(
                text=f"{icon} {SUNDAY_TASK.label}",
                callback_data=cb,
            )]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
