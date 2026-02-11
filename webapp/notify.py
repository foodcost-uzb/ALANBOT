"""Send Telegram notifications via Bot API (HTTP calls, no aiogram dependency)."""

from __future__ import annotations

import aiohttp

from bot.config import BOT_TOKEN

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


async def send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
    """Send a text message to a Telegram user. Returns True on success."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            ) as resp:
                return resp.status == 200
    except Exception:
        return False


async def get_file_url(file_id: str) -> str | None:
    """Get a download URL for a Telegram file_id."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/getFile",
                json={"file_id": file_id},
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                file_path = data.get("result", {}).get("file_path")
                if not file_path:
                    return None
                return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    except Exception:
        return None
