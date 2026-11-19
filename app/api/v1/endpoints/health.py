from fastapi import APIRouter
from app.core.config import get_settings
from app.services.ai_engine import ai_engine

router = APIRouter(tags=["Health & Telemetria"])


@router.get(
    "/health",
    summary="Healthcheck e status do motor de IA",
    description="Retorna o estado operacional do microsserviço e confirma se a sessão neural de recorte está carregada em memória.",
)
async def health_check() -> dict:
    settings = get_settings()
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "ai_engine": {
            "loaded": ai_engine.is_loaded,
            "engine_type": ai_engine.engine_type,
            "configured_model": ai_engine.model_name,
            "warm_up_time_ms": ai_engine.load_time_ms,
        },
        "capabilities": {
            "background_presets": [
                "clean_studio",
                "warm_bistro",
                "dark_slate",
                "rustic_wood",
                "transparent",
            ],
            "framing_presets": [
                "delivery_standard (1200x900)",
                "square_catalog (800x800)",
                "hd_showcase (1280x720)",
                "original",
            ],
            "output_formats": ["WEBP", "JPEG", "PNG"],
        },
    }
