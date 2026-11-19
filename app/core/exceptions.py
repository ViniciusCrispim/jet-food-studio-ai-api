from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from app.core.logging import logger


class ImageProcessingError(Exception):
    """Exceção base para falhas no processamento ou validação de imagem."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class UnsupportedMediaTypeError(ImageProcessingError):
    """Arquivo enviado não é uma imagem suportada."""

    def __init__(self, content_type: str | None, allowed: list[str]):
        super().__init__(
            message=f"Formato de arquivo não suportado ('{content_type}'). Envie JPEG, PNG ou WEBP.",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            details={"received_content_type": content_type, "allowed_types": allowed},
        )


class PayloadTooLargeError(ImageProcessingError):
    """Arquivo excede o limite máximo permitido."""

    def __init__(self, max_mb: int):
        super().__init__(
            message=f"A imagem excede o tamanho máximo permitido de {max_mb}MB.",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            details={"max_size_mb": max_mb},
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Registra handlers globais para respostas padronizadas de erro na API."""

    @app.exception_handler(ImageProcessingError)
    async def image_processing_exception_handler(request: Request, exc: ImageProcessingError) -> JSONResponse:
        logger.warning(f"Erro de validação/processamento em {request.url.path}: {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.message,
                "details": exc.details,
                "path": request.url.path,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Erro interno inesperado em {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": True,
                "message": "Erro interno ao processar a solicitação no estúdio de imagem.",
                "details": {"type": exc.__class__.__name__},
                "path": request.url.path,
            },
        )
