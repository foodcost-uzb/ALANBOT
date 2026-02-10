"""Pure scoring functions — no DB or I/O."""

from __future__ import annotations

from datetime import date

from .tasks_config import (
    DAILY_TASKS,
    MONEY_TIERS,
    POINTS_PER_TASK,
    SHOWER_KEY,
    SUNDAY_PENALTY,
    SUNDAY_TASK,
)


def calculate_daily_points(completed_keys: set[str]) -> int:
    """If shower not done, entire day = 0. Otherwise count completed daily tasks."""
    if SHOWER_KEY not in completed_keys:
        return 0
    return sum(
        POINTS_PER_TASK for t in DAILY_TASKS if t.key in completed_keys
    )


def get_money_percentage(total_points: int) -> int:
    for min_pts, max_pts, pct in MONEY_TIERS:
        if min_pts <= total_points <= max_pts:
            return pct
    return 0


def points_to_next_tier(total_points: int) -> tuple[int, int] | None:
    """Return (points_needed, next_percentage) or None if already at max."""
    sorted_tiers = sorted(MONEY_TIERS, key=lambda t: t[0])
    current_pct = get_money_percentage(total_points)
    for min_pts, _, pct in sorted_tiers:
        if pct > current_pct:
            deficit = min_pts - total_points
            if deficit > 0:
                return deficit, pct
    return None


def calculate_weekly_result(
    daily_completed: dict[str, set[str]],
    sunday_done: bool,
) -> dict:
    """
    daily_completed: {date_str: set of completed task keys} for 7 days.
    sunday_done: whether room_clean was completed on Sunday.
    Returns dict with daily_points, subtotal, penalty, total, money_percent.
    """
    daily_points: dict[str, int] = {}
    for day, keys in daily_completed.items():
        daily_points[day] = calculate_daily_points(keys)

    subtotal = sum(daily_points.values())
    penalty = SUNDAY_PENALTY if not sunday_done else 0
    total = max(subtotal - penalty, 0)
    money_percent = get_money_percentage(total)

    return {
        "daily_points": daily_points,
        "subtotal": subtotal,
        "penalty": penalty,
        "total": total,
        "money_percent": money_percent,
    }


def format_daily_summary(
    child_name: str,
    day: date,
    completed_keys: set[str],
    is_sunday: bool,
) -> str:
    points = calculate_daily_points(completed_keys)
    max_pts = len(DAILY_TASKS)

    lines = [
        f"📊 <b>Итоги дня ({day.strftime('%d.%m')})</b>",
        f"Ребёнок: {child_name}",
        "",
    ]

    for t in DAILY_TASKS:
        icon = "✅" if t.key in completed_keys else "❌"
        lines.append(f"{icon} {t.label}")

    if is_sunday:
        icon = "✅" if SUNDAY_TASK.key in completed_keys else "❌"
        lines.append(f"{icon} {SUNDAY_TASK.label}")

    if SHOWER_KEY not in completed_keys:
        lines.append("\n⚠️ Душ не принят — баллы за день: 0")
    else:
        lines.append(f"\nБаллы за день: {points}/{max_pts}")

    return "\n".join(lines)


def format_child_evening_summary(
    child_name: str,
    day: date,
    completed_keys: set[str],
    weekly_points_so_far: int,
    days_left: int,
) -> str:
    """Evening message for the child with today's score and weekly progress."""
    daily_pts = calculate_daily_points(completed_keys)
    max_daily = len(DAILY_TASKS)

    lines = [
        f"🌙 <b>Итоги твоего дня ({day.strftime('%d.%m')})</b>",
        "",
    ]

    if SHOWER_KEY not in completed_keys:
        lines.append("⚠️ Ты не принял душ — баллы за сегодня: 0")
    else:
        lines.append(f"Сегодня ты набрал: <b>{daily_pts}/{max_daily}</b> баллов")

    total = weekly_points_so_far + daily_pts
    lines.append(f"За неделю пока: <b>{total}</b> баллов")

    current_pct = get_money_percentage(total)
    lines.append(f"Сейчас твой уровень: <b>{current_pct}%</b> карманных денег")

    next_tier = points_to_next_tier(total)
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
) -> str:
    result = calculate_weekly_result(daily_completed, sunday_done)
    dp = result["daily_points"]

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
        max_pts = len(DAILY_TASKS)
        lines.append(f"  {weekday_name} {d.strftime('%d.%m')}: {pts}/{max_pts}")

    lines.append("")
    lines.append(f"Сумма: {result['subtotal']}")
    if result["penalty"]:
        lines.append(f"Штраф (уборка комнаты): -{result['penalty']}")
    lines.append(f"<b>Итого: {result['total']}</b>")
    lines.append(f"Карманные деньги: <b>{result['money_percent']}%</b>")

    return "\n".join(lines)
