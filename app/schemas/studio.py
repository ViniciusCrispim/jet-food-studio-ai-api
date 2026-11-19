from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class StudioBackgroundPreset(str, Enum):
    """Estratégias de fundo padronizado para cardápios de delivery."""

    CLEAN_STUDIO = "clean_studio"       # Fundo branco/off-white suave de estúdio (padrão de catálogo)
    WARM_BISTRO = "warm_bistro"         # Creme quente aconchegante (padarias, doces, massas, cafés)
    DARK_SLATE = "dark_slate"           # Ardósia escura gourmet (hambúrguer artesanal, sushi, carnes)
    RUSTIC_WOOD = "rustic_wood"         # Tom amadeirado quente (pizzas, churrasco, porções)
    TRANSPARENT = "transparent"         # Fundo 100% transparente (PNG/WEBP recortado)


class FramingPreset(str, Enum):
    """Padrões de proporção e resolução para aplicativos de delivery."""

    DELIVERY_STANDARD = "delivery_standard"   # 1200x900 (Proporção 4:3 recomendada para plataformas de delivery)
    SQUARE_CATALOG = "square_catalog"         # 800x800 (Proporção 1:1 para cards compactos e redes sociais)
    HD_SHOWCASE = "hd_showcase"               # 1280x720 (Proporção 16:9 para banners de destaque)
    ORIGINAL = "original"                     # Mantém as dimensões originais da foto enviada


class EnhancementIntensity(str, Enum):
    """Nível de intervenção no realce de iluminação, cor e nitidez do alimento."""

    SUBTLE = "subtle"                   # Correção leve (fotos já bem iluminadas)
    BALANCED = "balanced"               # Realce gastronômico equilibrado (recomendado)
    VIBRANT = "vibrant"                 # Recuperação intensa de luz, calor e textura


class OutputFormat(str, Enum):
    WEBP = "WEBP"
    JPEG = "JPEG"
    PNG = "PNG"


class StudioProcessOptions(BaseModel):
    """Opções configuráveis do Pipeline de Tratamento Gastronômico."""

    remove_background: bool = Field(
        default=True,
        description="Recorta o prato/alimento removendo o fundo original via IA (IS-Net / U²-Net).",
    )
    preserve_plate_rim: bool = Field(
        default=True,
        description="Reconstrói e preserva o contorno completo do prato/louça ao redor da comida para evitar efeito de comida flutuando.",
    )
    background_preset: StudioBackgroundPreset = Field(
        default=StudioBackgroundPreset.CLEAN_STUDIO,
        description="Fundo padronizado de estúdio a ser aplicado após o recorte.",
    )
    custom_bg_hex: Optional[str] = Field(
        default=None,
        description="Cor hexadecimal opcional (ex: '#F8F5F0') caso o restaurante queira a cor da sua marca.",
    )
    enhancement_intensity: EnhancementIntensity = Field(
        default=EnhancementIntensity.BALANCED,
        description="Intensidade da correção automática de luz (CLAHE), temperatura de cor e nitidez.",
    )
    add_contact_shadow: bool = Field(
        default=True,
        description="Projeta sombra suave de contato na base do prato para dar profundidade realista.",
    )
    framing_preset: FramingPreset = Field(
        default=FramingPreset.DELIVERY_STANDARD,
        description="Padronização de enquadramento e resolução para plataformas de delivery.",
    )
    padding_ratio: float = Field(
        default=0.12,
        ge=0.02,
        le=0.35,
        description="Margem de respiro ao redor do prato (0.12 = 12% de margem padrão de cardápio).",
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.WEBP,
        description="Formato final da imagem otimizada.",
    )
    output_quality: int = Field(
        default=92,
        ge=60,
        le=100,
        description="Qualidade de compressão da imagem final (60-100).",
    )
