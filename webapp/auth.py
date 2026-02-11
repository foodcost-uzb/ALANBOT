"""Telegram Mini App initData validation (HMAC-SHA256)."""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qs, unquote

from aiohttp import web

from bot.config import BOT_TOKEN
from .db import get_user_by_telegram_id


def _validate_init_data(init_data: str) -> dict | None:
    """Validate Telegram WebApp initData and return parsed data or None."""
    parsed = parse_qs(init_data, keep_blank_values=True)
    if "hash" not in parsed:
        return None

    received_hash = parsed.pop("hash")[0]

    # Build data-check-string: sorted key=value pairs
    data_check_parts = []
    for key in sorted(parsed.keys()):
        val = parsed[key][0]
        data_check_parts.append(f"{key}={val}")
    data_check_string = "\n".join(data_check_parts)

    # HMAC-SHA256 validation
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    # Extract user info
    user_data_raw = parsed.get("user", [None])[0]
    if not user_data_raw:
        return None

    try:
        user_data = json.loads(unquote(user_data_raw))
    except (json.JSONDecodeError, TypeError):
        return None

    return {
        "telegram_id": user_data.get("id"),
        "first_name": user_data.get("first_name", ""),
        "last_name": user_data.get("last_name", ""),
        "username": user_data.get("username", ""),
    }


@web.middleware
async def auth_middleware(request: web.Request, handler):
    """Middleware: validate Authorization header for /api/* routes."""
    if not request.path.startswith("/api/"):
        return await handler(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("tma "):
        return web.json_response({"error": "Missing authorization"}, status=401)

    init_data = auth_header[4:]
    tg_data = _validate_init_data(init_data)
    if not tg_data:
        return web.json_response({"error": "Invalid initData"}, status=401)

    telegram_id = tg_data["telegram_id"]
    if not telegram_id:
        return web.json_response({"error": "No user in initData"}, status=401)

    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        return web.json_response({"error": "User not registered"}, status=403)

    request["user"] = user
    request["tg_data"] = tg_data
    return await handler(request)
