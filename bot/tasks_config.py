"""Fixed daily tasks and scoring constants."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskDef:
    key: str
    label: str
    group: str  # "morning", "evening", "sunday"


DAILY_TASKS: tuple[TaskDef, ...] = (
    # Morning
    TaskDef("teeth", "Почистить зубы", "morning"),
    TaskDef("clothes", "Одеться", "morning"),
    TaskDef("bed", "Заправить кровать", "morning"),
    # Evening
    TaskDef("shower", "Принять душ", "evening"),
    TaskDef("underwear", "Сменить бельё", "evening"),
    TaskDef("laundry", "Положить вещи в стирку", "evening"),
    TaskDef("prep", "Подготовить одежду на завтра", "evening"),
    TaskDef("tidy", "Убрать за собой", "evening"),
)

SUNDAY_TASK = TaskDef("room_clean", "Уборка комнаты", "sunday")

SHOWER_KEY = "shower"

POINTS_PER_TASK = 1
SUNDAY_PENALTY = 5

# Weekly money tiers: (min_points, max_points, percentage)
MONEY_TIERS: tuple[tuple[int, int, int], ...] = (
    (50, 56, 100),
    (42, 49, 70),
    (35, 41, 40),
    (0, 34, 0),
)

MAX_WEEKLY_POINTS = 56  # 8 tasks * 7 days

GROUP_HEADERS = {
    "morning": "🌅 Утро",
    "evening": "🌙 Вечер",
    "sunday": "🧹 Воскресенье",
}

ALL_TASK_KEYS = {t.key for t in DAILY_TASKS} | {SUNDAY_TASK.key}
