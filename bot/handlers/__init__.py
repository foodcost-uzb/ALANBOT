from aiogram import Router

from .start import router as start_router
from .parent import router as parent_router
from .child import router as child_router


def get_all_routers() -> list[Router]:
    return [start_router, parent_router, child_router]
