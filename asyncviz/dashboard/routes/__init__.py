from fastapi import APIRouter

from asyncviz.dashboard.routes.assets import router as _assets_router
from asyncviz.dashboard.routes.configuration import router as _configuration_router
from asyncviz.dashboard.routes.executor import router as _executor_router
from asyncviz.dashboard.routes.executor_metrics import router as _executor_metrics_router
from asyncviz.dashboard.routes.gather import router as _gather_router
from asyncviz.dashboard.routes.health import router as _health_router
from asyncviz.dashboard.routes.packaging import router as _packaging_router
from asyncviz.dashboard.routes.queue_metrics import router as _queue_metrics_router
from asyncviz.dashboard.routes.queues import router as _queues_router
from asyncviz.dashboard.routes.runtime import router as _runtime_router
from asyncviz.dashboard.routes.semaphores import router as _semaphores_router
from asyncviz.dashboard.routes.websocket import router as websocket_router

api_router = APIRouter()
api_router.include_router(_health_router)
api_router.include_router(_runtime_router)
api_router.include_router(_packaging_router)
api_router.include_router(_configuration_router)
api_router.include_router(_assets_router)
api_router.include_router(_queues_router)
api_router.include_router(_queue_metrics_router)
api_router.include_router(_semaphores_router)
api_router.include_router(_gather_router)
api_router.include_router(_executor_router)
api_router.include_router(_executor_metrics_router)

__all__ = ["api_router", "websocket_router"]
