import base64
import io
import time
from typing import Optional
from fastapi import APIRouter, File, Form, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from app.api.v1.dependencies import validate_and_load_image
from app.schemas.studio import (
    EnhancementIntensity,
    FramingPreset,
    OutputFormat,
    StudioBackgroundPreset,
    StudioProcessOptions,
)
from app.services.pipeline.orchestrator import pipeline_orchestrator
from app.services.quality_analyzer import quality_analyzer

router = APIRouter(prefix="/studio", tags=["Estúdio Gastronômico IA (Processamento)"])


@router.post(
    "/process",
    summary="Processa e padroniza a foto do prato (Recorte IA + Correção de Luz/Cor + Fundo de Estúdio)",
    description=(
        "Executa o pipeline completo do Jet Food Studio IA e retorna o arquivo de imagem binário pronto "
        "para upload em catálogos ou S3/Backblaze B2, incluindo telemetria detalhada nos headers HTTP."
    ),
    responses={
        200: {
            "content": {
                "image/webp": {},
                "image/jpeg": {},
                "image/png": {},
            },
            "description": "Imagem gastronômica padronizada e otimizada.",
        }
    },
)
async def process_food_image(
    file: UploadFile = File(..., description="Foto original do prato (JPEG, PNG ou WEBP)"),
    remove_background: bool = Form(True, description="Recortar o prato removendo o fundo original via IA"),
    preserve_plate_rim: bool = Form(
        True,
        description="Preservar e reconstruir a borda completa do prato/louça ao redor da comida",
    ),
    background_preset: StudioBackgroundPreset = Form(
        StudioBackgroundPreset.CLEAN_STUDIO,
        description="Estilo de fundo padronizado de estúdio",
    ),
    custom_bg_hex: Optional[str] = Form(
        None,
        description="Cor hexadecimal opcional para o fundo (ex: #F8F5F0)",
    ),
    enhancement_intensity: EnhancementIntensity = Form(
        EnhancementIntensity.BALANCED,
        description="Intensidade do tratamento de luz, calor e nitidez (subtle, balanced, vibrant)",
    ),
    add_contact_shadow: bool = Form(
        True,
        description="Adicionar sombra realista de contato na base do prato",
    ),
    framing_preset: FramingPreset = Form(
        FramingPreset.DELIVERY_STANDARD,
        description="Enquadramento e proporção de saída (delivery_standard=1200x900, square_catalog=800x800, hd_showcase=1280x720, original)",
    ),
    padding_ratio: float = Form(
        0.12,
        ge=0.02,
        le=0.35,
        description="Margem de respiro ao redor do prato (0.02 a 0.35)",
    ),
    output_format: OutputFormat = Form(
        OutputFormat.WEBP,
        description="Formato do arquivo de saída (WEBP, JPEG, PNG)",
    ),
    output_quality: int = Form(
        92,
        ge=60,
        le=100,
        description="Qualidade da compressão (60 a 100)",
    ),
) -> Response:
    start_total = time.perf_counter()
    image = await validate_and_load_image(file)

    options = StudioProcessOptions(
        remove_background=remove_background,
        preserve_plate_rim=preserve_plate_rim,
        background_preset=background_preset,
        custom_bg_hex=custom_bg_hex,
        enhancement_intensity=enhancement_intensity,
        add_contact_shadow=add_contact_shadow,
        framing_preset=framing_preset,
        padding_ratio=padding_ratio,
        output_format=output_format,
        output_quality=output_quality,
    )

    # Executa pipeline CPU-bound no ThreadPool sem bloquear o loop assíncrono do FastAPI
    output_bytes, media_type, context = await run_in_threadpool(
        pipeline_orchestrator.execute, image, options
    )
    total_ms = round((time.perf_counter() - start_total) * 1000, 2)

    headers = {
        "X-Studio-Total-Time-Ms": str(total_ms),
        "X-Studio-Segmentation-Engine": context.metadata.get("segmentation_engine", "unknown"),
        "X-Studio-Final-Dimensions": context.metadata.get("final_dimensions", ""),
        "X-Studio-Step-Timings-Ms": ",".join(
            f"{k}:{v}" for k, v in context.step_timings_ms.items()
        ),
        "Content-Disposition": f'inline; filename="studio_dish.{output_format.value.lower()}"',
    }

    return Response(content=output_bytes, media_type=media_type, headers=headers)


@router.post(
    "/compare",
    summary="Executa Diagnóstico + Tratamento e retorna payload JSON (Antes vs. Depois em Base64)",
    description=(
        "Endpoint ideal para interfaces web e pré-visualização: analisa a foto original, "
        "aplica o pipeline completo e retorna o diagnóstico técnico junto com a imagem tratada "
        "e as métricas comparativas de antes e depois em uma única chamada."
    ),
)
async def compare_before_and_after(
    file: UploadFile = File(..., description="Foto original do prato"),
    remove_background: bool = Form(True),
    preserve_plate_rim: bool = Form(True),
    background_preset: StudioBackgroundPreset = Form(StudioBackgroundPreset.CLEAN_STUDIO),
    custom_bg_hex: Optional[str] = Form(None),
    enhancement_intensity: EnhancementIntensity = Form(EnhancementIntensity.BALANCED),
    add_contact_shadow: bool = Form(True),
    framing_preset: FramingPreset = Form(FramingPreset.DELIVERY_STANDARD),
    padding_ratio: float = Form(0.12),
    output_format: OutputFormat = Form(OutputFormat.WEBP),
    output_quality: int = Form(92),
) -> dict:
    start_total = time.perf_counter()
    image = await validate_and_load_image(file)

    options = StudioProcessOptions(
        remove_background=remove_background,
        preserve_plate_rim=preserve_plate_rim,
        background_preset=background_preset,
        custom_bg_hex=custom_bg_hex,
        enhancement_intensity=enhancement_intensity,
        add_contact_shadow=add_contact_shadow,
        framing_preset=framing_preset,
        padding_ratio=padding_ratio,
        output_format=output_format,
        output_quality=output_quality,
    )

    def _run_analysis_and_pipeline():
        before_analysis = quality_analyzer.analyze(image)
        output_bytes, media_type, context = pipeline_orchestrator.execute(image, options)
        after_analysis = quality_analyzer.analyze(context.current_image)
        return before_analysis, after_analysis, output_bytes, media_type, context

    (
        before_analysis,
        after_analysis,
        output_bytes,
        media_type,
        context,
    ) = await run_in_threadpool(_run_analysis_and_pipeline)

    total_ms = round((time.perf_counter() - start_total) * 1000, 2)
    b64_processed = base64.b64encode(output_bytes).decode("utf-8")

    return {
        "processing_time_ms": total_ms,
        "step_timings_ms": context.step_timings_ms,
        "segmentation_engine": context.metadata.get("segmentation_engine", "unknown"),
        "final_dimensions": context.metadata.get("final_dimensions", ""),
        "output_size_kb": round(len(output_bytes) / 1024, 1),
        "before_analysis": before_analysis,
        "after_analysis": after_analysis,
        "processed_image_data_url": f"data:{media_type};base64,{b64_processed}",
    }
