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
    verificando MIME type (ou extensão do arquivo), limite de tamanho (MB), integridade dos bytes,
    corrigindo orientação EXIF de câmeras de celular e otimizando dimensões muito grandes (>1600px).
    """
    settings = get_settings()

    content_type = (file.content_type or "").lower()
    filename = (file.filename or "").lower()
    valid_ext = filename.endswith((".jpg", ".jpeg", ".png", ".webp", ".jfif"))

    if content_type not in settings.ALLOWED_MIME_TYPES and not valid_ext:
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

        # Redimensiona preventivamente fotos gigantes de celular (ex: 4000x3000 / 12MP+)
        # para evitar consumo excessivo de RAM/CPU na rede neural mantendo alta definição
        max_dim = settings.MAX_PROCESSING_DIMENSION
        if max(image.width, image.height) > max_dim:
            scale = max_dim / float(max(image.width, image.height))
            new_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        return image
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageProcessingError(
            "Não foi possível decodificar a imagem enviada. Verifique se o arquivo é JPEG, PNG ou WEBP válido."
        ) from exc
