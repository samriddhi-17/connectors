from app.api.routes.alerts import router as alerts_router
from app.api.routes.connectors import router as connectors_router
from app.api.routes.health import router as health_router
from app.api.routes.query import router as query_router

__all__ = ["alerts_router", "connectors_router", "health_router", "query_router"]