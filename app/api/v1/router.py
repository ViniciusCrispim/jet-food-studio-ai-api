from fastapi import APIRouter
from app.api.v1.endpoints import analyze, guide, health, studio

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(health.router)
api_v1_router.include_router(guide.router)
api_v1_router.include_router(analyze.router)
api_v1_router.include_router(studio.router)
