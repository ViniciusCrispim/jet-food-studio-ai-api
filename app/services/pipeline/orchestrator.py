import io
import time
from typing import List, Tuple
from PIL import Image
from app.schemas.studio import OutputFormat, StudioProcessOptions
from app.services.pipeline.base import ImageContext, PipelineStep
from app.services.pipeline.steps import (
    BackgroundRemovalStep,
    FoodColorAndLightEnhancementStep,
    StudioFramingAndCompositionStep,
)


class FoodStudioPipelineOrchestrator:
    """
    Orquestrador do Pipeline de Processamento Gastronômico.
    Encadeia todas as etapas de transformação em memória (stateless) e coleta
    métricas de performance por etapa para observabilidade nos headers HTTP.
    """

    def __init__(self, steps: List[PipelineStep] | None = None) -> None:
        self.steps: List[PipelineStep] = steps or [
            BackgroundRemovalStep(),
            FoodColorAndLightEnhancementStep(),
            StudioFramingAndCompositionStep(),
        ]

    def execute(
        self, image: Image.Image, options: StudioProcessOptions
    ) -> Tuple[bytes, str, ImageContext]:
        """
        Executa todas as etapas do pipeline e codifica o resultado em memória (`BytesIO`).
        Retorna `(image_bytes, media_type, context)`.
        """
        context = ImageContext(
            original_image=image,
            current_image=image.copy(),
            options=options,
        )

        for step in self.steps:
            step_start = time.perf_counter()
            context = step.process(context)
            elapsed_ms = round((time.perf_counter() - step_start) * 1000, 2)
            context.step_timings_ms[step.name] = elapsed_ms

        image_bytes, media_type = self._encode_output(
            context.current_image,
            options.output_format,
            options.output_quality,
        )
        return image_bytes, media_type, context

    def _encode_output(
        self, image: Image.Image, output_format: OutputFormat, quality: int
    ) -> Tuple[bytes, str]:
        buffer = io.BytesIO()

        if output_format == OutputFormat.JPEG:
            # JPEG não suporta canal Alpha; achata sobre branco se necessário
            if image.mode in ("RGBA", "LA"):
                bg = Image.new("RGB", image.size, (255, 255, 255))
                bg.paste(image, mask=image.split()[-1])
                image = bg
            else:
                image = image.convert("RGB")
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
            media_type = "image/jpeg"
        elif output_format == OutputFormat.PNG:
            image.save(buffer, format="PNG", optimize=True)
            media_type = "image/png"
        else:
            image.save(buffer, format="WEBP", quality=quality, method=4)
            media_type = "image/webp"

        buffer.seek(0)
        return buffer.read(), media_type


pipeline_orchestrator = FoodStudioPipelineOrchestrator()
