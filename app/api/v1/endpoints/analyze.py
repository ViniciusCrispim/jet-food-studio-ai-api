from fastapi import APIRouter, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from app.api.v1.dependencies import validate_and_load_image
from app.schemas.analysis import PhotoAnalysisResponse
from app.services.quality_analyzer import quality_analyzer

router = APIRouter(tags=["Diagnóstico de Qualidade (Visão Computacional)"])


@router.post(
    "/analyze",
    response_model=PhotoAnalysisResponse,
    summary="Analisa a qualidade técnica de uma foto de comida e retorna diagnóstico completo",
    description=(
        "Executa análise por Visão Computacional (OpenCV) na foto enviada pelo vendedor, "
        "calculando notas de 0 a 100 para Iluminação, Nitidez/Foco, Contraste, Vivacidade de Cores "
        "e Resolução, além de sugerir os melhores parâmetros para o tratamento automático."
    ),
)
async def analyze_food_photo(
    file: UploadFile = File(..., description="Foto do prato/alimento em JPEG, PNG ou WEBP"),
) -> PhotoAnalysisResponse:
    image = await validate_and_load_image(file)
    # Executa análise OpenCV em threadpool para não bloquear o event loop assíncrono
    result = await run_in_threadpool(quality_analyzer.analyze, image)
    return result
