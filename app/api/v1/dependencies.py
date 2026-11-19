import io
from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from app.core.config import get_settings
from app.core.exceptions import (
    ImageProcessingError,
    PayloadTooLargeError,
    UnsupportedMediaTypeError,
)


async def validate_and_load_image(file: UploadFile) -> Image.Image:
    """
    Lê e valida o arquivo de imagem enviado pelo cliente em memória (`BytesIO`),
    verificando MIME type, limite de tamanho (MB), integridade dos bytes e
    corrigindo orientação EXIF de câmeras de celular automaticamente.
    """
    settings = get_settings()

    content_type = (file.content_type or "").lower()
    if content_type not in settings.ALLOWED_MIME_TYPES:
        raise UnsupportedMediaTypeError(content_type, settings.ALLOWED_MIME_TYPES)

    raw_bytes = await file.read()
    if not raw_bytes:
        raise ImageProcessingError("O arquivo enviado está vazio.")

    if len(raw_bytes) > settings.max_upload_bytes:
        raise PayloadTooLargeError(settings.MAX_UPLOAD_SIZE_MB)

    try:
        image = Image.open(io.BytesIO(raw_bytes))
        image.load()
        # Corrige rotação automática EXIF comum em fotos tiradas por smartphones
        image = ImageOps.exif_transpose(image)
        return image
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageProcessingError(
            "Não foi possível decodificar a imagem enviada. Verifique se o arquivo não está corrompido."
        ) from exc
