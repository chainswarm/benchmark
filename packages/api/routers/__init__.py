"""
Tournament API routers.

Exports FastAPI routers for the tournament system.
"""

from packages.api.routers.tournament_router import router as tournament_router
from packages.api.routers.registration_router import router as registration_router

__all__ = ["tournament_router", "registration_router"]