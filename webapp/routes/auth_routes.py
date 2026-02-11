"""Auth routes — GET /api/me."""

from __future__ import annotations

from aiohttp import web

routes = web.RouteTableDef()


@routes.get("/api/me")
async def get_me(request: web.Request) -> web.Response:
    user = request["user"]
    return web.json_response({
        "id": user["id"],
        "telegram_id": user["telegram_id"],
        "role": user["role"],
        "family_id": user["family_id"],
        "name": user["name"],
    })
