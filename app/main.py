from contextlib import asynccontextmanager
from pathlib import Path
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import logger
from app.services.ai_engine import ai_engine

settings = get_settings()
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida do microsserviço.
    Pré-aquece o modelo neural de segmentação em memória na subida do servidor
    (Singleton Warm-up) para eliminar latência de cold-start nas requisições.
    """
    logger.info(f"Iniciando {settings.APP_NAME} v{settings.APP_VERSION} [{settings.APP_ENV}]...")
    if settings.PRELOAD_AI_MODEL:
        ai_engine.warm_up()
    yield
    logger.info(f"Encerrando {settings.APP_NAME}...")


def create_application() -> FastAPI:
    """Application Factory Pattern para instanciação limpa e testável do FastAPI."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Process-Time-Ms",
            "X-Studio-Total-Time-Ms",
            "X-Studio-Segmentation-Engine",
            "X-Studio-Final-Dimensions",
            "X-Studio-Step-Timings-Ms",
        ],
    )

    @app.middleware("http")
    async def process_time_middleware(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
        return response

    register_exception_handlers(app)
    app.include_router(api_v1_router)

    @app.get("/", include_in_schema=False)
    async def serve_interactive_studio():
        """Serve o Playground Web Interativo (Estúdio Antes/Depois + Diagnóstico + Guia)."""
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_application()
