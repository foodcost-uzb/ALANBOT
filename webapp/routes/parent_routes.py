"""Parent API routes — dashboard, approvals, reports, task management."""

from __future__ import annotations

from datetime import date, timedelta

from aiohttp import web

from bot.scoring import (
    calculate_daily_points,
    calculate_weekly_result,
    get_money_percentage,
    points_to_next_tier,
)
from bot.tasks_config import SHOWER_KEY, SUNDAY_TASK, TaskDef, GROUP_HEADERS
from webapp.db import (
    add_custom_child_task,
    add_extra_task,
    approve_completion,
    approve_extra_task,
    delete_approval_messages,
    delete_family,
    get_approval_messages,
    get_child_all_tasks,
    get_child_enabled_tasks,
    get_completed_keys_for_date,
    get_completed_keys_for_range,
    get_completion_by_id,
    get_extra_points_for_date,
    get_extra_points_for_range,
    get_extra_task,
    get_extra_tasks_for_date,
    get_family_children,
    get_family_invite_code,
    get_family_parents,
    get_pending_approvals,
    get_pending_keys_for_date,
    get_user_by_id,
    reject_completion,
    reject_extra_task,
    remove_custom_child_task,
    reset_child_tasks,
    toggle_child_task,
)
from webapp.notify import edit_message_caption, send_message

routes = web.RouteTableDef()

HISTORY_WEEKS = 4


def _require_parent(request: web.Request) -> dict:
    user = request["user"]
    if user["role"] != "parent":
        raise web.HTTPForbidden(text="Parent only")
    return user


def _child_has_shower(tasks: list[dict]) -> bool:
    return any(t["task_key"] == SHOWER_KEY for t in tasks)


def _child_has_sunday(tasks: list[dict]) -> bool:
    return any(t["task_key"] == SUNDAY_TASK.key for t in tasks)


def _tasks_to_taskdefs(tasks: list[dict], exclude_sunday: bool = True) -> tuple[TaskDef, ...]:
    return tuple(
        TaskDef(key=t["task_key"], label=t["label"], group=t["task_group"])
        for t in tasks
        if not (exclude_sunday and t["task_group"] == "sunday")
    )


# ── Children list with progress ─────────────────────────


@routes.get("/api/children")
async def get_children(request: web.Request) -> web.Response:
    user = _require_parent(request)
    children = await get_family_children(user["family_id"])
    today_str = date.today().isoformat()

    result = []
    for child in children:
        enabled = await get_child_enabled_tasks(child["id"])
        daily_tasks = [t for t in enabled if t["task_group"] != "sunday"]
        completed = await get_completed_keys_for_date(child["id"], today_str)
        pending = await get_pending_keys_for_date(child["id"], today_str)
        total = len(daily_tasks)
        done = sum(1 for t in daily_tasks if t["task_key"] in completed)
        pend = sum(1 for t in daily_tasks if t["task_key"] in pending)
        result.append({
            "id": child["id"],
            "name": child["name"],
            "telegram_id": child["telegram_id"],
            "total_tasks": total,
            "done": done,
            "pending": pend,
        })

    # Also get pending approval count and parents list
    approvals = await get_pending_approvals(user["family_id"])
    parents = await get_family_parents(user["family_id"])

    return web.json_response({
        "children": result,
        "parents": [{"id": p["id"], "name": p["name"]} for p in parents],
        "pending_approvals": len(approvals),
    })


# ── Today's progress for a child ────────────────────────


@routes.get("/api/today/{child_id}")
async def get_today(request: web.Request) -> web.Response:
    user = _require_parent(request)
    child_id = int(request.match_info["child_id"])

    # Verify child belongs to family
    children = await get_family_children(user["family_id"])
    child = next((c for c in children if c["id"] == child_id), None)
    if not child:
        return web.json_response({"error": "Child not found"}, status=404)

    today = date.today()
    today_str = today.isoformat()
    is_sunday = today.weekday() == 6

    enabled = await get_child_enabled_tasks(child_id)
    completed = await get_completed_keys_for_date(child_id, today_str)
    pending = await get_pending_keys_for_date(child_id, today_str)
    extras = await get_extra_tasks_for_date(child_id, today_str)
    extra_pts = await get_extra_points_for_date(child_id, today_str)

    daily_tasks = _tasks_to_taskdefs(enabled, exclude_sunday=True)
    shower_req = _child_has_shower(enabled)

    points = calculate_daily_points(completed, daily_tasks, shower_req)

    tasks = []
    for t in enabled:
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
        elif et["completed"]:
            status = "pending"
        else:
            status = "todo"
        extra_list.append({
            "id": et["id"],
            "title": et["title"],
            "points": et["points"],
            "status": status,
        })

    shower_missing = shower_req and SHOWER_KEY not in completed

    return web.json_response({
        "child_name": child["name"],
        "date": today_str,
        "is_sunday": is_sunday,
        "tasks": tasks,
        "extras": extra_list,
        "points": points,
        "max_points": len(daily_tasks),
        "extra_points": extra_pts,
        "shower_missing": shower_missing,
    })


# ── Weekly report ───────────────────────────────────────


@routes.get("/api/report/{child_id}")
async def get_report(request: web.Request) -> web.Response:
    user = _require_parent(request)
    child_id = int(request.match_info["child_id"])

    children = await get_family_children(user["family_id"])
    child = next((c for c in children if c["id"] == child_id), None)
    if not child:
        return web.json_response({"error": "Child not found"}, status=404)

    today = date.today()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)

    enabled = await get_child_enabled_tasks(child_id)
    daily_tasks = _tasks_to_taskdefs(enabled, exclude_sunday=True)
    shower_req = _child_has_shower(enabled)
    has_sunday = _child_has_sunday(enabled)

    daily_completed = await get_completed_keys_for_range(child_id, start.isoformat(), end.isoformat())
    for i in range(7):
        d = (start + timedelta(days=i)).isoformat()
        daily_completed.setdefault(d, set())

    sunday_str = end.isoformat()
    sunday_done = has_sunday and SUNDAY_TASK.key in daily_completed.get(sunday_str, set())

    result = calculate_weekly_result(daily_completed, sunday_done, daily_tasks, shower_req)

    extra_pts = await get_extra_points_for_range(child_id, start.isoformat(), end.isoformat())
    total_extra = sum(extra_pts.values())

    day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    days = []
    sorted_days = sorted(result["daily_points"].keys())
    for day_str in sorted_days:
        d = date.fromisoformat(day_str)
        days.append({
            "date": day_str,
            "weekday": day_names[d.weekday()],
            "display": d.strftime("%d.%m"),
            "points": result["daily_points"][day_str],
            "extra": extra_pts.get(day_str, 0),
        })

    return web.json_response({
        "child_name": child["name"],
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": days,
        "subtotal": result["subtotal"],
        "penalty": result["penalty"],
        "total": result["total"],
        "extra_total": total_extra,
        "money_percent": result["money_percent"],
        "max_daily": len(daily_tasks),
    })


# ── History (last 4 weeks) ─────────────────────────────


@routes.get("/api/history/{child_id}")
async def get_history(request: web.Request) -> web.Response:
    user = _require_parent(request)
    child_id = int(request.match_info["child_id"])

    children = await get_family_children(user["family_id"])
    child = next((c for c in children if c["id"] == child_id), None)
    if not child:
        return web.json_response({"error": "Child not found"}, status=404)

    today = date.today()
    current_week_start = today - timedelta(days=today.weekday())

    enabled = await get_child_enabled_tasks(child_id)
    daily_tasks = _tasks_to_taskdefs(enabled, exclude_sunday=True)
    shower_req = _child_has_shower(enabled)
    has_sunday = _child_has_sunday(enabled)

    weeks = []
    for w in range(1, HISTORY_WEEKS + 1):
        start = current_week_start - timedelta(weeks=w)
        end = start + timedelta(days=6)

        daily_completed = await get_completed_keys_for_range(child_id, start.isoformat(), end.isoformat())
        for i in range(7):
            d = (start + timedelta(days=i)).isoformat()
            daily_completed.setdefault(d, set())

        sunday_str = end.isoformat()
        sunday_done = has_sunday and SUNDAY_TASK.key in daily_completed.get(sunday_str, set())

        result = calculate_weekly_result(daily_completed, sunday_done, daily_tasks, shower_req)
        extra_pts = await get_extra_points_for_range(child_id, start.isoformat(), end.isoformat())
        total_extra = sum(extra_pts.values())

        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        days = []
        for day_str in sorted(result["daily_points"].keys()):
            d = date.fromisoformat(day_str)
            days.append({
                "date": day_str,
                "weekday": day_names[d.weekday()],
                "display": d.strftime("%d.%m"),
                "points": result["daily_points"][day_str],
            })

        weeks.append({
            "start": start.isoformat(),
            "end": end.isoformat(),
            "start_display": start.strftime("%d.%m"),
            "end_display": end.strftime("%d.%m"),
            "days": days,
            "subtotal": result["subtotal"],
            "penalty": result["penalty"],
            "total": result["total"],
            "extra_total": total_extra,
            "money_percent": result["money_percent"],
            "max_daily": len(daily_tasks),
        })

    return web.json_response({
        "child_name": child["name"],
        "weeks": weeks,
    })


# ── Approvals ───────────────────────────────────────────


@routes.get("/api/approvals")
async def get_approvals(request: web.Request) -> web.Response:
    user = _require_parent(request)
    approvals = await get_pending_approvals(user["family_id"])

    result = []
    for a in approvals:
        item = {
            "id": a["id"],
            "type": a["type"],
            "child_name": a["child_name"],
            "child_id": a["child_id"],
            "date": a["date"],
            "photo_file_id": a.get("photo_file_id"),
            "media_type": a.get("media_type", "photo"),
        }
        if a["type"] == "task":
            # Get task label
            enabled = await get_child_enabled_tasks(a["child_id"])
            label = a["task_key"]
            for t in enabled:
                if t["task_key"] == a["task_key"]:
                    label = t["label"]
                    break
            item["label"] = label
            item["task_key"] = a["task_key"]
        else:
            item["label"] = a["title"]
            item["points"] = a["points"]

        result.append(item)

    return web.json_response({"approvals": result})


async def _update_all_approval_messages(approval_type: str, approval_id: int, new_caption: str) -> None:
    """Edit approval messages for all parents in Telegram (remove buttons)."""
    messages = await get_approval_messages(approval_type, approval_id)
    for msg in messages:
        try:
            await edit_message_caption(msg["chat_id"], msg["message_id"], new_caption)
        except Exception:
            pass
    await delete_approval_messages(approval_type, approval_id)


@routes.post("/api/approvals/{id}/approve")
async def approve_route(request: web.Request) -> web.Response:
    user = _require_parent(request)
    approval_id = int(request.match_info["id"])

    body = await request.json() if request.content_length else {}
    approval_type = body.get("type", "task")

    if approval_type == "extra":
        et = await get_extra_task(approval_id)
        if not et:
            return web.json_response({"error": "Not found"}, status=404)
        await approve_extra_task(approval_id)
        child = await get_user_by_id(et["child_id"])
        child_name = child["name"] if child else "Ребёнок"
        new_caption = f"✅ Одобрено: {child_name} — <b>{et['title']}</b> (+{et['points']} б.)"
        if child:
            await send_message(child["telegram_id"], f"✅ Доп. задание «{et['title']}» одобрено родителем! (+{et['points']} б.)")
        await _update_all_approval_messages("extra", approval_id, new_caption)
    else:
        completion = await get_completion_by_id(approval_id)
        if not completion:
            return web.json_response({"error": "Not found"}, status=404)
        await approve_completion(approval_id)
        child = await get_user_by_id(completion["child_id"])
        child_name = child["name"] if child else "Ребёнок"
        enabled = await get_child_enabled_tasks(completion["child_id"])
        label = completion["task_key"]
        for t in enabled:
            if t["task_key"] == completion["task_key"]:
                label = t["label"]
                break
        new_caption = f"✅ Одобрено: {child_name} — <b>{label}</b>"
        if child:
            await send_message(child["telegram_id"], f"✅ Задача «{label}» одобрена родителем!")
        await _update_all_approval_messages("task", approval_id, new_caption)

    return web.json_response({"ok": True})


@routes.post("/api/approvals/{id}/reject")
async def reject_route(request: web.Request) -> web.Response:
    user = _require_parent(request)
    approval_id = int(request.match_info["id"])

    body = await request.json() if request.content_length else {}
    approval_type = body.get("type", "task")

    if approval_type == "extra":
        et = await get_extra_task(approval_id)
        if not et:
            return web.json_response({"error": "Not found"}, status=404)
        await reject_extra_task(approval_id)
        child = await get_user_by_id(et["child_id"])
        child_name = child["name"] if child else "Ребёнок"
        new_caption = f"❌ Отклонено: {child_name} — <b>{et['title']}</b>"
        if child:
            await send_message(child["telegram_id"], f"❌ Доп. задание «{et['title']}» отклонено. Попробуй снова!")
        await _update_all_approval_messages("extra", approval_id, new_caption)
    else:
        completion = await get_completion_by_id(approval_id)
        if not completion:
            return web.json_response({"error": "Not found"}, status=404)
        child = await get_user_by_id(completion["child_id"])
        child_name = child["name"] if child else "Ребёнок"
        label = completion["task_key"]
        if child:
            enabled = await get_child_enabled_tasks(completion["child_id"])
            for t in enabled:
                if t["task_key"] == completion["task_key"]:
                    label = t["label"]
                    break
        new_caption = f"❌ Отклонено: {child_name} — <b>{label}</b>"
        await reject_completion(approval_id)
        if child:
            await send_message(child["telegram_id"], f"❌ Задача «{label}» отклонена. Попробуй выполнить снова!")
        await _update_all_approval_messages("task", approval_id, new_caption)

    return web.json_response({"ok": True})


# ── Extra tasks — assign to child ──────────────────────


@routes.post("/api/extras")
async def create_extra(request: web.Request) -> web.Response:
    user = _require_parent(request)
    body = await request.json()

    child_id = body.get("child_id")
    title = body.get("title", "").strip()
    points = body.get("points", 1)

    if not child_id or not title:
        return web.json_response({"error": "child_id and title required"}, status=400)

    children = await get_family_children(user["family_id"])
    child = next((c for c in children if c["id"] == child_id), None)
    if not child:
        return web.json_response({"error": "Child not found"}, status=404)

    try:
        points = max(1, int(points))
    except (ValueError, TypeError):
        points = 1

    today_str = date.today().isoformat()
    task_id = await add_extra_task(user["family_id"], child_id, title, points, today_str)

    # Notify child
    await send_message(
        child["telegram_id"],
        f"⭐ Новое доп. задание от родителя!\n<b>{title}</b> (+{points} б.)",
    )

    return web.json_response({"ok": True, "id": task_id})


# ── Task management ─────────────────────────────────────


@routes.get("/api/tasks/{child_id}")
async def get_tasks(request: web.Request) -> web.Response:
    user = _require_parent(request)
    child_id = int(request.match_info["child_id"])

    children = await get_family_children(user["family_id"])
    child = next((c for c in children if c["id"] == child_id), None)
    if not child:
        return web.json_response({"error": "Child not found"}, status=404)

    tasks = await get_child_all_tasks(child_id)
    return web.json_response({
        "child_name": child["name"],
        "tasks": [
            {
                "key": t["task_key"],
                "label": t["label"],
                "group": t["task_group"],
                "is_standard": bool(t["is_standard"]),
                "enabled": bool(t["enabled"]),
            }
            for t in tasks
        ],
    })


@routes.post("/api/tasks/{child_id}/toggle")
async def toggle_task(request: web.Request) -> web.Response:
    user = _require_parent(request)
    child_id = int(request.match_info["child_id"])

    children = await get_family_children(user["family_id"])
    if not any(c["id"] == child_id for c in children):
        return web.json_response({"error": "Child not found"}, status=404)

    body = await request.json()
    task_key = body.get("task_key")
    enabled = body.get("enabled")

    if task_key is None or enabled is None:
        return web.json_response({"error": "task_key and enabled required"}, status=400)

    await toggle_child_task(child_id, task_key, bool(enabled))
    return web.json_response({"ok": True})


@routes.post("/api/tasks/{child_id}/add")
async def add_task(request: web.Request) -> web.Response:
    user = _require_parent(request)
    child_id = int(request.match_info["child_id"])

    children = await get_family_children(user["family_id"])
    if not any(c["id"] == child_id for c in children):
        return web.json_response({"error": "Child not found"}, status=404)

    body = await request.json()
    label = body.get("label", "").strip()
    if not label:
        return web.json_response({"error": "label required"}, status=400)

    task_key = await add_custom_child_task(child_id, label)
    return web.json_response({"ok": True, "task_key": task_key})


@routes.post("/api/tasks/{child_id}/delete")
async def delete_task(request: web.Request) -> web.Response:
    user = _require_parent(request)
    child_id = int(request.match_info["child_id"])

    children = await get_family_children(user["family_id"])
    if not any(c["id"] == child_id for c in children):
        return web.json_response({"error": "Child not found"}, status=404)

    body = await request.json()
    task_key = body.get("task_key")
    if not task_key:
        return web.json_response({"error": "task_key required"}, status=400)

    await remove_custom_child_task(child_id, task_key)
    return web.json_response({"ok": True})


@routes.post("/api/tasks/{child_id}/reset")
async def reset_tasks(request: web.Request) -> web.Response:
    user = _require_parent(request)
    child_id = int(request.match_info["child_id"])

    children = await get_family_children(user["family_id"])
    if not any(c["id"] == child_id for c in children):
        return web.json_response({"error": "Child not found"}, status=404)

    await reset_child_tasks(child_id)
    return web.json_response({"ok": True})


# ── Invite code ─────────────────────────────────────────


@routes.get("/api/invite")
async def get_invite(request: web.Request) -> web.Response:
    user = _require_parent(request)
    code = await get_family_invite_code(user["family_id"])
    return web.json_response({"invite_code": code})


# ── Reset family ───────────────────────────────────────


@routes.post("/api/family/reset")
async def reset_family(request: web.Request) -> web.Response:
    user = _require_parent(request)
    family_id = user["family_id"]
    telegram_ids = await delete_family(family_id)

    # Notify other family members via Telegram
    for tg_id in telegram_ids:
        if tg_id != user["telegram_id"]:
            try:
                await send_message(
                    tg_id,
                    "ℹ️ Семья была сброшена родителем.\n"
                    "Для повторной регистрации нажмите /start.",
                )
            except Exception:
                pass

    return web.json_response({"ok": True})
