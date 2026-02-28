import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Almaty")
MORNING_HOUR: int = int(os.getenv("MORNING_HOUR", "7"))
MORNING_MINUTE: int = int(os.getenv("MORNING_MINUTE", "0"))
REMINDER_HOURS: list[int] = [
    int(h) for h in os.getenv("REMINDER_HOURS", "12,17").split(",")
]
DEADLINE_HOUR: int = int(os.getenv("DEADLINE_HOUR", "22"))
PARENT_PASSWORD: str = os.getenv("PARENT_PASSWORD", "1234")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "bot.db"
