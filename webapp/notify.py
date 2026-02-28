"""Send Telegram notifications via Bot API (HTTP calls, no aiogram dependency)."""

from __future__ import annotations

from pathlib import Path

import aiohttp

from bot.config import BOT_TOKEN

API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


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


async def send_photo(
    chat_id: int,
    photo_path: str,
    caption: str = "",
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
) -> bool:
    """Send a photo to a Telegram user. photo_path is a local uploads/ path."""
    try:
        local_file = DATA_DIR / photo_path
        if not local_file.exists():
            return await send_message(chat_id, caption, parse_mode)

        data = aiohttp.FormData()
        data.add_field("chat_id", str(chat_id))
        data.add_field("caption", caption)
        data.add_field("parse_mode", parse_mode)
        with open(local_file, "rb") as f:
            file_data = f.read()
        data.add_field(
            "photo",
            file_data,
            filename=local_file.name,
            content_type="image/jpeg",
        )
        if reply_markup:
            import json
            data.add_field("reply_markup", json.dumps(reply_markup))

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_BASE}/sendPhoto", data=data) as resp:
                return resp.status == 200
    except Exception:
        return await send_message(chat_id, caption, parse_mode)


async def send_video(
    chat_id: int,
    video_path: str,
    caption: str = "",
    parse_mode: str = "HTML",
    reply_markup: dict | None = None,
) -> bool:
    """Send a video to a Telegram user. video_path is a local uploads/ path."""
    try:
        local_file = DATA_DIR / video_path
        if not local_file.exists():
            return await send_message(chat_id, caption, parse_mode)

        data = aiohttp.FormData()
        data.add_field("chat_id", str(chat_id))
        data.add_field("caption", caption)
        data.add_field("parse_mode", parse_mode)
        with open(local_file, "rb") as f:
            file_data = f.read()
        data.add_field(
            "video",
            file_data,
            filename=local_file.name,
            content_type="video/mp4",
        )
        if reply_markup:
            import json
            data.add_field("reply_markup", json.dumps(reply_markup))

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_BASE}/sendVideo", data=data) as resp:
                return resp.status == 200
    except Exception:
        return await send_message(chat_id, caption, parse_mode)


async def send_media_to_parent(
    chat_id: int,
    file_id_or_path: str,
    media_type: str,
    caption: str,
    completion_id: int,
    is_extra: bool = False,
) -> int | None:
    """Send photo/video with approval buttons to a parent.
    Handles both Telegram file_ids and local upload paths.
    Returns the Telegram message_id on success, None on failure.
    Also saves the approval_message for cross-parent sync.
    """
    # Build inline keyboard for approval
    if is_extra:
        approve_cb = f"approve_extra:{completion_id}"
        reject_cb = f"reject_extra:{completion_id}"
    else:
        approve_cb = f"approve_task:{completion_id}"
        reject_cb = f"reject_task:{completion_id}"

    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ Одобрить", "callback_data": approve_cb},
            {"text": "❌ Отклонить", "callback_data": reject_cb},
        ]]
    }

    message_id = None

    # Local upload path
    if file_id_or_path.startswith("uploads/"):
        if media_type == "video":
            message_id = await _send_media_get_id(chat_id, file_id_or_path, "video", caption, reply_markup)
        else:
            message_id = await _send_media_get_id(chat_id, file_id_or_path, "photo", caption, reply_markup)
    else:
        # Telegram file_id — send directly via API
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "chat_id": chat_id,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "reply_markup": reply_markup,
                }
                if media_type == "video":
                    payload["video"] = file_id_or_path
                    url = f"{API_BASE}/sendVideo"
                else:
                    payload["photo"] = file_id_or_path
                    url = f"{API_BASE}/sendPhoto"

                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        message_id = data.get("result", {}).get("message_id")
        except Exception:
            await send_message(chat_id, caption)

    # Save approval message for cross-parent sync
    if message_id:
        from webapp.db import get_db
        approval_type = "extra" if is_extra else "task"
        db = await get_db()
        await db.execute(
            "INSERT INTO approval_messages (approval_type, approval_id, chat_id, message_id) VALUES (?, ?, ?, ?)",
            (approval_type, completion_id, chat_id, message_id),
        )
        await db.commit()

    return message_id


async def _send_media_get_id(
    chat_id: int, file_path: str, media_key: str, caption: str, reply_markup: dict
) -> int | None:
    """Send local media file and return Telegram message_id."""
    local_file = DATA_DIR / file_path
    if not local_file.exists():
        await send_message(chat_id, caption)
        return None

    import json as json_mod
    data = aiohttp.FormData()
    data.add_field("chat_id", str(chat_id))
    data.add_field("caption", caption)
    data.add_field("parse_mode", "HTML")
    data.add_field("reply_markup", json_mod.dumps(reply_markup))

    content_type = "video/mp4" if media_key == "video" else "image/jpeg"
    with open(local_file, "rb") as f:
        file_data = f.read()
    data.add_field(
        media_key,
        file_data,
        filename=local_file.name,
        content_type=content_type,
    )

    endpoint = "sendVideo" if media_key == "video" else "sendPhoto"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{API_BASE}/{endpoint}", data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("result", {}).get("message_id")
    except Exception:
        await send_message(chat_id, caption)
    return None


async def edit_message_caption(
    chat_id: int, message_id: int, caption: str, parse_mode: str = "HTML"
) -> bool:
    """Edit caption of an existing message (removes inline keyboard)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/editMessageCaption",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "caption": caption,
                    "parse_mode": parse_mode,
                },
            ) as resp:
                return resp.status == 200
    except Exception:
        return False


async def send_checklist_to_child(telegram_id: int) -> bool:
    """Trigger checklist send to a child via the bot's sendMessage.

    This is a lightweight notification — the child can also press /checklist.
    """
    return await send_message(
        telegram_id,
        "📋 Чеклист обновлён — нажми /checklist чтобы увидеть изменения.",
    )


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
