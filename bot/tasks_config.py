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

# Weekly money tiers: (min_points, max_points, percentage) — legacy fixed tiers
MONEY_TIERS: tuple[tuple[int, int, int], ...] = (
    (50, 56, 100),
    (42, 49, 70),
    (35, 41, 40),
    (0, 34, 0),
)

MAX_WEEKLY_POINTS = 56  # 8 tasks * 7 days

# Adaptive tier thresholds: (fraction_of_max, money_percentage)
# Tiers adapt to the number of enabled tasks per child
# Fractions chosen so that ceil(56 * fraction) reproduces original fixed tiers
TIER_THRESHOLDS: tuple[tuple[float, int], ...] = (
    (0.892, 100),   # ≥89.2% → 100% money (50/56 for 8 tasks)
    (0.75,   70),   # ≥75%   → 70%  money (42/56 for 8 tasks)
    (0.625,  40),   # ≥62.5% → 40%  money (35/56 for 8 tasks)
)

GROUP_HEADERS = {
    "morning": "🌅 Утро",
    "evening": "🌙 Вечер",
    "sunday": "🧹 Воскресенье",
    "custom": "📝 Свои задачи",
}

ALL_TASK_KEYS = {t.key for t in DAILY_TASKS} | {SUNDAY_TASK.key}

# Motivational messages for reminders (randomly picked)
REMINDER_MESSAGES: tuple[str, ...] = (
    "Дружок, не забудь выполнить задания! Мама и папа расстроятся, если не сделаешь.",
    "Эй, дружище! Осталось совсем немного — давай закончим все задачи!",
    "Ты молодец, но есть ещё невыполненные задания. Не подведи маму и папу!",
    "Помни: каждая выполненная задача — шаг к карманным деньгам!",
    "Время летит! Не забудь отметить задачи, пока день не закончился.",
    "Дружок, мама и папа верят в тебя! Заверши оставшиеся задания.",
    "Ещё чуть-чуть и все задачи будут выполнены! Ты справишься!",
    "Не откладывай на потом — выполни задания сейчас и будь спокоен!",
)
