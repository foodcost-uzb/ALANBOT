"""aiohttp web server entry point for ALANBOT Mini App."""

from __future__ import annotations

import os
from pathlib import Path

from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

from .auth import auth_middleware
from .db import close_db
from .routes.auth_routes import routes as auth_routes
from .routes.child_routes import routes as child_routes
from .routes.parent_routes import routes as parent_routes

WEBAPP_PORT = int(os.getenv("WEBAPP_PORT", "8081"))
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "data" / "uploads"


async def on_shutdown(app: web.Application) -> None:
    await close_db()


def create_app() -> web.Application:
    app = web.Application(middlewares=[auth_middleware])

    # API routes
    app.router.add_routes(auth_routes)
    app.router.add_routes(child_routes)
    app.router.add_routes(parent_routes)

    # Serve uploaded files
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    app.router.add_static("/uploads/", path=str(UPLOADS_DIR), name="uploads")

    # Static files (SPA)
    app.router.add_static("/static/", path=str(STATIC_DIR), name="static")

    # SPA fallback: serve index.html for all non-API, non-static routes
    async def index_handler(request: web.Request) -> web.FileResponse:
        return web.FileResponse(STATIC_DIR / "index.html")

    app.router.add_get("/", index_handler)
    app.router.add_get("/{path:(?!api/|static/|uploads/).*}", index_handler)

    app.on_shutdown.append(on_shutdown)
    return app


def main() -> None:
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=WEBAPP_PORT)


if __name__ == "__main__":
    main()
