from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict
from PIL import Image
from app.schemas.studio import StudioProcessOptions


@dataclass
class ImageContext:
    """
    Contexto mutável que trafega através das etapas do Pipeline (Chain of Responsibility),
    armazenando a imagem atual, opções do usuário e telemetria de tempo por etapa.
    """

    original_image: Image.Image
    current_image: Image.Image
    options: StudioProcessOptions
    step_timings_ms: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)


class PipelineStep(ABC):
    """Interface abstrata para cada etapa do pipeline de tratamento de imagem."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Identificador único da etapa para telemetria e logs."""
        raise NotImplementedError

    @abstractmethod
    def process(self, context: ImageContext) -> ImageContext:
        """Executa a transformação na imagem contida no contexto."""
        raise NotImplementedError
