"""Child API routes — checklist, complete/uncomplete tasks, photo upload."""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path

import aiohttp
from aiohttp import web

from bot.tasks_config import SHOWER_KEY, TaskDef
from webapp.db import (
    complete_extra_task,
    complete_task,
    ensure_child_tasks_initialized,
    get_child_enabled_tasks,
    get_completed_keys_for_date,
    get_extra_task,
    get_extra_tasks_for_date,
    get_pending_keys_for_date,
    uncomplete_extra_task,
    uncomplete_task,
    get_family_parents,
)
from webapp.notify import get_file_url, send_media_to_parent

routes = web.RouteTableDef()

UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"


def _require_child(request: web.Request) -> dict:
    user = request["user"]
    if user["role"] != "child":
        raise web.HTTPForbidden(text="Child only")
    return user


def _is_sunday(d: date | None = None) -> bool:
    return (d or date.today()).weekday() == 6


@routes.get("/api/checklist")
async def get_checklist(request: web.Request) -> web.Response:
    user = _require_child(request)
    today = date.today()
    today_str = today.isoformat()
    is_sunday = _is_sunday(today)

    await ensure_child_tasks_initialized(user["id"])
    tasks_rows = await get_child_enabled_tasks(user["id"])
    completed = await get_completed_keys_for_date(user["id"], today_str)
    pending = await get_pending_keys_for_date(user["id"], today_str)
    extras = await get_extra_tasks_for_date(user["id"], today_str)

    tasks = []
    for t in tasks_rows:
        if t["task_group"] == "sunday" and not is_sunday:
            continue
        status = "done" if t["task_key"] in completed else ("pending" if t["task_key"] in pending else "todo")
        tasks.append({
            "key": t["task_key"],
            "label": t["label"],
            "group": t["task_group"],
            "status": status,
        })

    extra_list = []
    for et in extras:
        if et["completed"] and et.get("approved"):
            status = "done"
        elif et["completed"] and not et.get("approved"):
            status = "pending"
        else:
            status = "todo"
        extra_list.append({
            "id": et["id"],
            "title": et["title"],
            "points": et["points"],
            "status": status,
        })

    return web.json_response({
        "date": today_str,
        "is_sunday": is_sunday,
        "tasks": tasks,
        "extras": extra_list,
    })


@routes.post("/api/checklist/{task_key}/complete")
async def complete_task_route(request: web.Request) -> web.Response:
    user = _require_child(request)
    task_key = request.match_info["task_key"]
    today_str = date.today().isoformat()

    # Validate task key belongs to child
    tasks_rows = await get_child_enabled_tasks(user["id"])
    valid_keys = {t["task_key"] for t in tasks_rows}
    if task_key not in valid_keys:
        return web.json_response({"error": "Invalid task"}, status=400)

    # Handle multipart file upload
    reader = await request.multipart()
    file_path = None
    media_type = "photo"

    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == "file":
            content_type = part.headers.get("Content-Type", "image/jpeg")
            media_type = "video" if "video" in content_type else "photo"
            ext = "mp4" if media_type == "video" else "jpg"
            day_dir = UPLOADS_DIR / today_str
            day_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{uuid.uuid4().hex}.{ext}"
            full_path = day_dir / filename
            with open(full_path, "wb") as f:
                while True:
                    chunk = await part.read_chunk()
                    if not chunk:
                        break
                    f.write(chunk)
            file_path = f"uploads/{today_str}/{filename}"

    if not file_path:
        return web.json_response({"error": "No file uploaded"}, status=400)

    completion_id = await complete_task(user["id"], task_key, today_str, file_path, media_type)

    # Get task label
    label = task_key
    for t in tasks_rows:
        if t["task_key"] == task_key:
            label = t["label"]
            break

    # Notify parents with photo + approval buttons (same as bot)
    caption = f"\ud83d\udd50 {user['name']} \u0432\u044b\u043f\u043e\u043b\u043d\u0438\u043b(\u0430): <b>{label}</b>\n\u041e\u0436\u0438\u0434\u0430\u0435\u0442 \u043e\u0434\u043e\u0431\u0440\u0435\u043d\u0438\u044f"
    parents = await get_family_parents(user["family_id"])
    for parent in parents:
        await send_media_to_parent(
            parent["telegram_id"], file_path, media_type,
            caption, completion_id, is_extra=False,
        )

    return web.json_response({"ok": True, "completion_id": completion_id, "status": "pending"})


@routes.post("/api/checklist/{task_key}/uncomplete")
async def uncomplete_task_route(request: web.Request) -> web.Response:
    user = _require_child(request)
    task_key = request.match_info["task_key"]
    today_str = date.today().isoformat()
    await uncomplete_task(user["id"], task_key, today_str)
    return web.json_response({"ok": True})


@routes.post("/api/extras/{extra_id}/complete")
async def complete_extra_route(request: web.Request) -> web.Response:
    user = _require_child(request)
    extra_id = int(request.match_info["extra_id"])
    today_str = date.today().isoformat()

    et = await get_extra_task(extra_id)
    if not et or et["child_id"] != user["id"]:
        return web.json_response({"error": "Not found"}, status=404)

    reader = await request.multipart()
    file_path = None
    media_type = "photo"

    while True:
        part = await reader.next()
        if part is None:
            break
        if part.name == "file":
            content_type = part.headers.get("Content-Type", "image/jpeg")
            media_type = "video" if "video" in content_type else "photo"
            ext = "mp4" if media_type == "video" else "jpg"
            day_dir = UPLOADS_DIR / today_str
            day_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{uuid.uuid4().hex}.{ext}"
            full_path = day_dir / filename
            with open(full_path, "wb") as f:
                while True:
                    chunk = await part.read_chunk()
                    if not chunk:
                        break
                    f.write(chunk)
            file_path = f"uploads/{today_str}/{filename}"

    if not file_path:
        return web.json_response({"error": "No file uploaded"}, status=400)

    await complete_extra_task(extra_id, file_path, media_type)

    # Notify parents with photo + approval buttons (same as bot)
    caption = f"\ud83d\udd50 {user['name']} \u0432\u044b\u043f\u043e\u043b\u043d\u0438\u043b(\u0430): <b>{et['title']}</b>\n\u041e\u0436\u0438\u0434\u0430\u0435\u0442 \u043e\u0434\u043e\u0431\u0440\u0435\u043d\u0438\u044f"
    parents = await get_family_parents(user["family_id"])
    for parent in parents:
        await send_media_to_parent(
            parent["telegram_id"], file_path, media_type,
            caption, extra_id, is_extra=True,
        )

    return web.json_response({"ok": True, "status": "pending"})


@routes.post("/api/extras/{extra_id}/uncomplete")
async def uncomplete_extra_route(request: web.Request) -> web.Response:
    user = _require_child(request)
    extra_id = int(request.match_info["extra_id"])
    et = await get_extra_task(extra_id)
    if not et or et["child_id"] != user["id"]:
        return web.json_response({"error": "Not found"}, status=404)
    await uncomplete_extra_task(extra_id)
    return web.json_response({"ok": True})


@routes.get("/api/media/{file_id:.+}")
async def proxy_media(request: web.Request) -> web.Response:
    """Proxy Telegram file_id or serve local upload."""
    file_id = request.match_info["file_id"]

    # Local upload
    if file_id.startswith("uploads/"):
        local_path = Path(__file__).resolve().parent.parent.parent / "data" / file_id
        if local_path.exists():
            return web.FileResponse(local_path)
        return web.json_response({"error": "File not found"}, status=404)

    # Telegram file_id — proxy through Bot API
    url = await get_file_url(file_id)
    if not url:
        return web.json_response({"error": "Cannot get file"}, status=404)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return web.json_response({"error": "Download failed"}, status=502)
            data = await resp.read()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            return web.Response(body=data, content_type=content_type)
