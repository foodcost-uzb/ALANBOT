"""Pure scoring functions — no DB or I/O."""

from __future__ import annotations

from datetime import date
from math import ceil

from .tasks_config import (
    DAILY_TASKS,
    POINTS_PER_TASK,
    SHOWER_KEY,
    SUNDAY_PENALTY,
    SUNDAY_TASK,
    TIER_THRESHOLDS,
    TaskDef,
)


def calculate_daily_points(
    completed_keys: set[str],
    daily_tasks: tuple[TaskDef, ...] | None = None,
    shower_required: bool = True,
) -> int:
    """If shower not done (and required), entire day = 0. Otherwise count completed daily tasks."""
    if shower_required and SHOWER_KEY not in completed_keys:
        return 0
    tasks = daily_tasks if daily_tasks is not None else DAILY_TASKS
    return sum(POINTS_PER_TASK for t in tasks if t.key in completed_keys)


def calculate_daily_total(
    completed_keys: set[str],
    extra_points: int,
    daily_tasks: tuple[TaskDef, ...] | None = None,
    shower_required: bool = True,
) -> int:
    """Daily points (base tasks) + extra bonus points."""
    return calculate_daily_points(completed_keys, daily_tasks, shower_required) + extra_points


def get_money_percentage(total_points: int, max_weekly_points: int | None = None) -> int:
    """Compute money percentage using adaptive thresholds.

    If max_weekly_points is given, thresholds are computed dynamically.
    Otherwise falls back to default max (len(DAILY_TASKS) * 7).
    """
    if max_weekly_points is None:
        max_weekly_points = len(DAILY_TASKS) * 7

    if max_weekly_points <= 0:
        return 0

    for fraction, pct in TIER_THRESHOLDS:
        threshold = ceil(max_weekly_points * fraction)
        if total_points >= threshold:
            return pct
    return 0


def points_to_next_tier(total_points: int, max_weekly_points: int | None = None) -> tuple[int, int] | None:
    """Return (points_needed, next_percentage) or None if already at max."""
    if max_weekly_points is None:
        max_weekly_points = len(DAILY_TASKS) * 7

    current_pct = get_money_percentage(total_points, max_weekly_points)

    # Sort thresholds ascending by percentage
    sorted_tiers = sorted(TIER_THRESHOLDS, key=lambda t: t[1])
    for fraction, pct in sorted_tiers:
        if pct > current_pct:
            threshold = ceil(max_weekly_points * fraction)
            deficit = threshold - total_points
            if deficit > 0:
                return deficit, pct
    return None


def calculate_weekly_result(
    daily_completed: dict[str, set[str]],
    sunday_done: bool,
    daily_tasks: tuple[TaskDef, ...] | None = None,
    shower_required: bool = True,
    extra_points_per_day: dict[str, int] | None = None,
    max_weekly_points: int | None = None,
) -> dict:
    """
    daily_completed: {date_str: set of completed task keys} for 7 days.
    sunday_done: whether room_clean was completed on Sunday.
    extra_points_per_day: {date_str: extra_points} for bonus tasks.
    max_weekly_points: max possible base points for the week (len(daily_tasks) * 7).
    Returns dict with daily_points, subtotal, penalty, extra_total, total, money_percent.
    """
    tasks = daily_tasks if daily_tasks is not None else DAILY_TASKS
    if max_weekly_points is None:
        max_weekly_points = len(tasks) * 7

    extra_per_day = extra_points_per_day or {}

    daily_points: dict[str, int] = {}
    for day, keys in daily_completed.items():
        daily_points[day] = calculate_daily_points(keys, daily_tasks, shower_required)

    subtotal = sum(daily_points.values())
    extra_total = sum(extra_per_day.values())
    penalty = SUNDAY_PENALTY if not sunday_done else 0
    total = max(subtotal + extra_total - penalty, 0)
    money_percent = min(get_money_percentage(total, max_weekly_points), 100)

    return {
        "daily_points": daily_points,
        "subtotal": subtotal,
        "extra_total": extra_total,
        "penalty": penalty,
        "total": total,
        "money_percent": money_percent,
    }


def format_daily_summary(
    child_name: str,
    day: date,
    completed_keys: set[str],
    is_sunday: bool,
    daily_tasks: tuple[TaskDef, ...] | None = None,
    sunday_task: TaskDef | None = SUNDAY_TASK,
    shower_required: bool = True,
    extra_points: int = 0,
) -> str:
    tasks = daily_tasks if daily_tasks is not None else DAILY_TASKS
    points = calculate_daily_points(completed_keys, tasks, shower_required)
    max_pts = len(tasks)

    lines = [
        f"📊 <b>Итоги дня ({day.strftime('%d.%m')})</b>",
        f"Ребёнок: {child_name}",
        "",
    ]

    for t in tasks:
        if t.group == "sunday":
            continue
        icon = "✅" if t.key in completed_keys else "❌"
        lines.append(f"{icon} {t.label}")

    if is_sunday and sunday_task:
        icon = "✅" if sunday_task.key in completed_keys else "❌"
        lines.append(f"{icon} {sunday_task.label}")

    if shower_required and SHOWER_KEY not in completed_keys:
        lines.append("\n⚠️ Душ не принят — баллы за день: 0")
    else:
        lines.append(f"\nБаллы за день: {points}/{max_pts}")

    if extra_points > 0:
        total = points + extra_points
        lines.append(f"⭐ Доп. задания: +{extra_points}")
        lines.append(f"<b>Всего за день: {total}</b>")

    return "\n".join(lines)


def format_child_evening_summary(
    child_name: str,
    day: date,
    completed_keys: set[str],
    weekly_points_so_far: int,
    days_left: int,
    daily_tasks: tuple[TaskDef, ...] | None = None,
    shower_required: bool = True,
    extra_points_today: int = 0,
    extra_weekly: int = 0,
    max_weekly_points: int | None = None,
) -> str:
    """Evening message for the child with today's score and weekly progress."""
    tasks = daily_tasks if daily_tasks is not None else DAILY_TASKS
    daily_pts = calculate_daily_points(completed_keys, tasks, shower_required)
    max_daily = len(tasks)
    if max_weekly_points is None:
        max_weekly_points = len(tasks) * 7

    lines = [
        f"🌙 <b>Итоги твоего дня ({day.strftime('%d.%m')})</b>",
        "",
    ]

    if shower_required and SHOWER_KEY not in completed_keys:
        lines.append("⚠️ Ты не принял душ — баллы за сегодня: 0")
    else:
        lines.append(f"Сегодня ты набрал: <b>{daily_pts}/{max_daily}</b> баллов")

    if extra_points_today > 0:
        lines.append(f"⭐ Доп. задания: +{extra_points_today}")

    today_total = daily_pts + extra_points_today
    total = weekly_points_so_far + today_total
    lines.append(f"За неделю пока: <b>{total}</b> баллов")

    current_pct = get_money_percentage(total, max_weekly_points)
    lines.append(f"Сейчас твой уровень: <b>{current_pct}%</b> карманных денег")

    next_tier = points_to_next_tier(total, max_weekly_points)
    if next_tier:
        deficit, next_pct = next_tier
        if days_left > 0:
            lines.append(
                f"\nДо <b>{next_pct}%</b> не хватает <b>{deficit}</b> баллов "
                f"(осталось {days_left} дн.)."
            )
            lines.append(
                "Попроси маму или папу дать дополнительное задание, "
                "чтобы не испортить рейтинг!"
            )
        else:
            lines.append(f"\nДо <b>{next_pct}%</b> не хватило <b>{deficit}</b> баллов.")
    elif current_pct == 100:
        lines.append("\nТы на максимуме — так держать! 🎉")

    return "\n".join(lines)


def format_weekly_report(
    child_name: str,
    start: date,
    end: date,
    daily_completed: dict[str, set[str]],
    sunday_done: bool,
    daily_tasks: tuple[TaskDef, ...] | None = None,
    sunday_task: TaskDef | None = SUNDAY_TASK,
    shower_required: bool = True,
    extra_points_per_day: dict[str, int] | None = None,
    max_weekly_points: int | None = None,
) -> str:
    result = calculate_weekly_result(
        daily_completed, sunday_done, daily_tasks, shower_required,
        extra_points_per_day=extra_points_per_day,
        max_weekly_points=max_weekly_points,
    )
    dp = result["daily_points"]
    tasks = daily_tasks if daily_tasks is not None else DAILY_TASKS
    max_pts = len(tasks)
    extra_per_day = extra_points_per_day or {}
    extra_total = result["extra_total"]

    lines = [
        f"📊 <b>Отчёт за неделю ({start.strftime('%d.%m')} — {end.strftime('%d.%m')})</b>",
        f"Ребёнок: {child_name}",
        "",
    ]

    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    sorted_days = sorted(dp.keys())
    for day_str in sorted_days:
        d = date.fromisoformat(day_str)
        weekday_name = day_names[d.weekday()]
        pts = dp[day_str]
        extra = extra_per_day.get(day_str, 0)
        extra_str = f" +{extra}⭐" if extra > 0 else ""
        lines.append(f"  {weekday_name} {d.strftime('%d.%m')}: {pts}/{max_pts}{extra_str}")

    lines.append("")
    lines.append(f"Сумма: {result['subtotal']}")
    if extra_total > 0:
        lines.append(f"⭐ Доп. задания: +{extra_total}")
    if result["penalty"]:
        lines.append(f"Штраф (уборка комнаты): -{result['penalty']}")
    lines.append(f"<b>Итого: {result['total']}</b>")
    lines.append(f"Карманные деньги: <b>{result['money_percent']}%</b>")

    return "\n".join(lines)
