import logging
from datetime import date, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import EVENING_HOUR, EVENING_MINUTE, MORNING_HOUR, MORNING_MINUTE, TIMEZONE
from .database import (
    get_all_families,
    get_completed_keys_for_date,
    get_completed_keys_for_range,
    get_family_children,
    get_family_parents,
)
from .handlers.child import send_checklist
from .scoring import format_daily_summary, format_weekly_report
from .tasks_config import SUNDAY_TASK

logger = logging.getLogger(__name__)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    # Morning checklist
    scheduler.add_job(
        morning_checklist,
        CronTrigger(hour=MORNING_HOUR, minute=MORNING_MINUTE, timezone=TIMEZONE),
        args=[bot],
        id="morning_checklist",
        replace_existing=True,
    )

    # Evening summary at 21:00 (configurable)
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


async def evening_summary(bot: Bot) -> None:
    """Send daily summary to all parents at evening."""
    logger.info("Sending evening summaries")
    today = date.today()
    today_str = today.isoformat()
    is_sunday = today.weekday() == 6

    families = await get_all_families()
    for family in families:
        children = await get_family_children(family["id"])
        parents = await get_family_parents(family["id"])
        for child in children:
            completed = await get_completed_keys_for_date(child["id"], today_str)
            text = format_daily_summary(child["name"], today, completed, is_sunday)
            for parent in parents:
                try:
                    await bot.send_message(
                        parent["telegram_id"], text, parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(
                        "Failed to send summary to %s: %s",
                        parent["telegram_id"],
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
            sunday_done = SUNDAY_TASK.key in daily_completed.get(sunday_str, set())

            text = format_weekly_report(
                child["name"], start, end, daily_completed, sunday_done
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
