from __future__ import annotations

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
    completed_keys: set[str],
    is_sunday: bool = False,
    extra_tasks: list[dict] | None = None,
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

    if extra_tasks:
        buttons.append(
            [InlineKeyboardButton(text="⭐ Доп. задания", callback_data="noop")]
        )
        for et in extra_tasks:
            done = bool(et["completed"])
            icon = "✅" if done else "⬜"
            cb = f"exdone:{et['id']}" if done else f"excheck:{et['id']}"
            buttons.append(
                [InlineKeyboardButton(
                    text=f"{icon} {et['title']} (+{et['points']} б.)",
                    callback_data=cb,
                )]
            )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Parent: child picker ─────────────────────────────────


def child_picker_kb(children: list[dict], prefix: str) -> InlineKeyboardMarkup:
    """Inline keyboard to pick a child. prefix is added before child id."""
    buttons = [
        [InlineKeyboardButton(
            text=c["name"],
            callback_data=f"{prefix}:{c['id']}",
        )]
        for c in children
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
