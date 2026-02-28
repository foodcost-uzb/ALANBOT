from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .tasks_config import DAILY_TASKS, GROUP_HEADERS, SUNDAY_TASK, TaskDef


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


def parent_join_kb() -> InlineKeyboardMarkup:
    """Choose between creating a new family or joining an existing one."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆕 Создать новую семью", callback_data="parent:new"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔗 Присоединиться к существующей", callback_data="parent:join"
                ),
            ],
        ]
    )


# ── Child: checklist ──────────────────────────────────────


def checklist_kb(
    completed_keys: set[str],
    pending_keys: set[str] | None = None,
    is_sunday: bool = False,
    extra_tasks: list[dict] | None = None,
    daily_tasks: tuple[TaskDef, ...] | None = None,
    sunday_task: TaskDef = SUNDAY_TASK,
) -> InlineKeyboardMarkup:
    if pending_keys is None:
        pending_keys = set()

    tasks = daily_tasks if daily_tasks is not None else DAILY_TASKS

    buttons: list[list[InlineKeyboardButton]] = []

    current_group = None
    for t in tasks:
        if t.group in ("sunday", "custom"):
            continue
        if t.group != current_group:
            current_group = t.group
            header = GROUP_HEADERS.get(current_group, current_group)
            buttons.append(
                [InlineKeyboardButton(
                    text=header,
                    callback_data="noop",
                )]
            )
        if t.key in completed_keys:
            icon = "✅"
            cb = f"done:{t.key}"
        elif t.key in pending_keys:
            icon = "🕐"
            cb = f"pending:{t.key}"
        else:
            icon = "⬜"
            cb = f"check:{t.key}"
        buttons.append(
            [InlineKeyboardButton(text=f"{icon} {t.label}", callback_data=cb)]
        )

    # Sunday task
    has_sunday = any(t.group == "sunday" for t in tasks)
    if is_sunday and has_sunday:
        buttons.append(
            [InlineKeyboardButton(
                text=GROUP_HEADERS.get("sunday", "🧹 Воскресенье"),
                callback_data="noop",
            )]
        )
        if sunday_task.key in completed_keys:
            icon = "✅"
            cb = f"done:{sunday_task.key}"
        elif sunday_task.key in pending_keys:
            icon = "🕐"
            cb = f"pending:{sunday_task.key}"
        else:
            icon = "⬜"
            cb = f"check:{sunday_task.key}"
        buttons.append(
            [InlineKeyboardButton(
                text=f"{icon} {sunday_task.label}",
                callback_data=cb,
            )]
        )

    # Custom tasks (non-standard, non-sunday from child_tasks)
    custom_tasks = [t for t in tasks if t.group == "custom"]
    if custom_tasks:
        buttons.append(
            [InlineKeyboardButton(text="📝 Свои задачи", callback_data="noop")]
        )
        for t in custom_tasks:
            if t.key in completed_keys:
                icon = "✅"
                cb = f"done:{t.key}"
            elif t.key in pending_keys:
                icon = "🕐"
                cb = f"pending:{t.key}"
            else:
                icon = "⬜"
                cb = f"check:{t.key}"
            buttons.append(
                [InlineKeyboardButton(text=f"{icon} {t.label}", callback_data=cb)]
            )

    if extra_tasks:
        buttons.append(
            [InlineKeyboardButton(text="⭐ Доп. задания", callback_data="noop")]
        )
        for et in extra_tasks:
            if et["completed"] and et.get("approved"):
                icon = "✅"
                cb = f"exdone:{et['id']}"
            elif et["completed"] and not et.get("approved"):
                icon = "🕐"
                cb = f"expending:{et['id']}"
            else:
                icon = "⬜"
                cb = f"excheck:{et['id']}"
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


# ── Parent: approval buttons ─────────────────────────────


def approval_kb(completion_id: int, is_extra: bool = False) -> InlineKeyboardMarkup:
    """Inline keyboard with Approve / Reject buttons for parent."""
    if is_extra:
        approve_cb = f"approve_extra:{completion_id}"
        reject_cb = f"reject_extra:{completion_id}"
    else:
        approve_cb = f"approve_task:{completion_id}"
        reject_cb = f"reject_task:{completion_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=approve_cb),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=reject_cb),
            ]
        ]
    )


# ── Parent: task manager ─────────────────────────────────


def task_manager_kb(child_id: int, tasks: list[dict]) -> InlineKeyboardMarkup:
    """Keyboard for managing a child's tasks (/tasks command)."""
    buttons: list[list[InlineKeyboardButton]] = []

    for t in tasks:
        icon = "✅" if t["enabled"] else "⬜"
        label = f"{icon} {t['label']}"
        row: list[InlineKeyboardButton] = [
            InlineKeyboardButton(
                text=label,
                callback_data=f"tmtoggle:{child_id}:{t['task_key']}",
            )
        ]
        # Allow deleting custom tasks
        if not t["is_standard"]:
            row.append(
                InlineKeyboardButton(
                    text="✖",
                    callback_data=f"tmdelete:{child_id}:{t['task_key']}",
                )
            )
        buttons.append(row)

    # Action buttons
    buttons.append([
        InlineKeyboardButton(
            text="➕ Добавить задачу",
            callback_data=f"tmadd:{child_id}",
        ),
    ])
    buttons.append([
        InlineKeyboardButton(
            text="↩ Сбросить к стандартным",
            callback_data=f"tmreset:{child_id}",
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
