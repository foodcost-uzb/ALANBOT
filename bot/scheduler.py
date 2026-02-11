import logging
import random
from datetime import date, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .child_tasks import (
    child_has_shower,
    child_has_sunday_task,
    get_active_daily_tasks,
)
from .config import (
    EVENING_HOUR,
    EVENING_MINUTE,
    MORNING_HOUR,
    MORNING_MINUTE,
    REMINDER_HOURS,
    TIMEZONE,
)
from .database import (
    get_all_families,
    get_completed_keys_for_date,
    get_completed_keys_for_range,
    get_family_children,
    get_family_parents,
)
from .handlers.child import send_checklist
from .scoring import (
    calculate_daily_points,
    format_child_evening_summary,
    format_daily_summary,
    format_weekly_report,
)
from .tasks_config import REMINDER_MESSAGES, SUNDAY_TASK

logger = logging.getLogger(__name__)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Morning checklist at 7:00
    scheduler.add_job(
        morning_checklist,
        CronTrigger(hour=MORNING_HOUR, minute=MORNING_MINUTE, timezone=TIMEZONE),
        args=[bot],
        id="morning_checklist",
        replace_existing=True,
    )

    # Reminders for incomplete tasks (default: 12:00, 17:00)
    for i, hour in enumerate(REMINDER_HOURS):
        scheduler.add_job(
            send_reminders,
            CronTrigger(hour=hour, minute=0, timezone=TIMEZONE),
            args=[bot],
            id=f"reminder_{i}",
            replace_existing=True,
        )

    # Evening summary at 21:00 — to parents AND child
    scheduler.add_job(
        evening_summary,
        CronTrigger(hour=EVENING_HOUR, minute=EVENING_MINUTE, timezone=TIMEZONE),
        args=[bot],
        id="evening_summary",
        replace_existing=True,
    )

    # Weekly report: Sunday at 20:00
    scheduler.add_job(
        weekly_report,
        CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=TIMEZONE),
        args=[bot],
        id="weekly_report",
        replace_existing=True,
    )

    return scheduler


async def morning_checklist(bot: Bot) -> None:
    """Send checklist to all children in all families."""
    logger.info("Sending morning checklists")
    families = await get_all_families()
    for family in families:
        children = await get_family_children(family["id"])
        for child in children:
            try:
                await send_checklist(bot, child["telegram_id"])
            except Exception as e:
                logger.error(
                    "Failed to send checklist to %s: %s",
                    child["telegram_id"],
                    e,
                )


async def send_reminders(bot: Bot) -> None:
    """Send motivational reminders to children with incomplete tasks."""
    logger.info("Sending reminders")
    today = date.today()
    today_str = today.isoformat()

    families = await get_all_families()
    for family in families:
        children = await get_family_children(family["id"])
        for child in children:
            try:
                completed = await get_completed_keys_for_date(child["id"], today_str)
                daily_tasks = await get_active_daily_tasks(child["id"])
                all_daily_keys = {t.key for t in daily_tasks}
                remaining = all_daily_keys - completed
                if not remaining:
                    continue

                msg = random.choice(REMINDER_MESSAGES)
                remaining_count = len(remaining)
                text = (
                    f"{msg}\n\n"
                    f"⬜ Осталось задач: <b>{remaining_count}</b> из {len(daily_tasks)}"
                )
                await bot.send_message(
                    child["telegram_id"], text, parse_mode="HTML"
                )
            except Exception as e:
                logger.error(
                    "Failed to send reminder to %s: %s",
                    child["telegram_id"],
                    e,
                )


async def evening_summary(bot: Bot) -> None:
    """Send daily summary to parents + child evening report with deficit."""
    logger.info("Sending evening summaries")
    today = date.today()
    today_str = today.isoformat()
    is_sunday = today.weekday() == 6

    # Days left in the week (today is already counted)
    days_left = 6 - today.weekday()  # 0=Mon..6=Sun

    # Week start (Monday)
    week_start = today - timedelta(days=today.weekday())

    families = await get_all_families()
    for family in families:
        children = await get_family_children(family["id"])
        parents = await get_family_parents(family["id"])
        for child in children:
            try:
                completed_today = await get_completed_keys_for_date(
                    child["id"], today_str
                )
                daily_tasks = await get_active_daily_tasks(child["id"])
                shower_req = await child_has_shower(child["id"])
                has_sunday = await child_has_sunday_task(child["id"])

                # Parent summary
                parent_text = format_daily_summary(
                    child["name"],
                    today,
                    completed_today,
                    is_sunday and has_sunday,
                    daily_tasks=daily_tasks,
                    shower_required=shower_req,
                )
                for parent in parents:
                    try:
                        await bot.send_message(
                            parent["telegram_id"], parent_text, parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to send summary to parent %s: %s",
                            parent["telegram_id"],
                            e,
                        )

                # Calculate weekly points so far (excluding today)
                weekly_points_so_far = 0
                for i in range(today.weekday()):
                    d = (week_start + timedelta(days=i)).isoformat()
                    day_keys = await get_completed_keys_for_date(child["id"], d)
                    weekly_points_so_far += calculate_daily_points(
                        day_keys, daily_tasks, shower_req
                    )

                # Child evening summary
                child_text = format_child_evening_summary(
                    child["name"],
                    today,
                    completed_today,
                    weekly_points_so_far,
                    days_left,
                    daily_tasks=daily_tasks,
                    shower_required=shower_req,
                )
                await bot.send_message(
                    child["telegram_id"], child_text, parse_mode="HTML"
                )
            except Exception as e:
                logger.error(
                    "Failed to send evening summary for child %s: %s",
                    child["telegram_id"],
                    e,
                )


async def weekly_report(bot: Bot) -> None:
    """Send weekly report to all parents."""
    logger.info("Sending weekly reports")
    today = date.today()
    start = today - timedelta(days=today.weekday())  # Monday
    end = start + timedelta(days=6)  # Sunday

    families = await get_all_families()
    for family in families:
        children = await get_family_children(family["id"])
        parents = await get_family_parents(family["id"])
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

            daily_tasks = await get_active_daily_tasks(child["id"])
            shower_req = await child_has_shower(child["id"])

            text = format_weekly_report(
                child["name"], start, end, daily_completed, sunday_done,
                daily_tasks=daily_tasks,
                shower_required=shower_req,
            )
            for parent in parents:
                try:
                    await bot.send_message(
                        parent["telegram_id"], text, parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(
                        "Failed to send report to %s: %s",
                        parent["telegram_id"],
                        e,
                    )
