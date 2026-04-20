from .advisory import router as advisory_router
from .control_plane import router as control_plane_router
from .health import router as health_router
from .profiles import router as profiles_router
from .simulation import router as simulation_router
from .trade_requests import router as trade_requests_router

__all__ = ["advisory_router", "control_plane_router", "health_router", "profiles_router", "simulation_router", "trade_requests_router"]
