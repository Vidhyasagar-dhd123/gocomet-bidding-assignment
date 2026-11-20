from fastapi import APIRouter

from app.api.routes import health, rfqs, suppliers

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(suppliers.router)
api_router.include_router(rfqs.router)
api_router.include_router(rfqs.events_router)
