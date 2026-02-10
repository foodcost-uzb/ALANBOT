import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Almaty")
MORNING_HOUR: int = int(os.getenv("MORNING_HOUR", "8"))
MORNING_MINUTE: int = int(os.getenv("MORNING_MINUTE", "0"))
EVENING_HOUR: int = int(os.getenv("EVENING_HOUR", "21"))
EVENING_MINUTE: int = int(os.getenv("EVENING_MINUTE", "0"))
PARENT_PASSWORD: str = os.getenv("PARENT_PASSWORD", "1234")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "bot.db"
