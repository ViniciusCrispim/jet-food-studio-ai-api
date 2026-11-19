import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from app.schemas.studio import (
    EnhancementIntensity,
    FramingPreset,
    StudioBackgroundPreset,
)
from app.services.ai_engine import ai_engine
from app.services.pipeline.base import ImageContext, PipelineStep
from app.services.studio_generator import studio_generator


class BackgroundRemovalStep(PipelineStep):
    """Etapa 1: Isola o prato/alimento removendo o fundo via IA (U²-Net / GrabCut)."""

    @property
    def name(self) -> str:
        return "background_removal"

    def process(self, context: ImageContext) -> ImageContext:
        if not context.options.remove_background:
            context.current_image = context.current_image.convert("RGBA")
            context.metadata["segmentation_engine"] = "bypassed"
            return context

        context.current_image = ai_engine.remove_background(context.current_image)
        context.metadata["segmentation_engine"] = ai_engine.engine_type
        return context


class FoodColorAndLightEnhancementStep(PipelineStep):
    """
    Etapa 2: Realce Gastronômico no espaço de cor CIE LAB.
    - Aplica CLAHE no canal L (Luminância) para recuperar detalhes em sombras sem alterar matizes.
    - Aquece sutilmente os canais A e B (realçando dourados, assados, queijos e molhos).
    - Aplica Unsharp Mask para destacar texturas apetitosas (crosta, gergelim, brilho).
    """

    INTENSITY_PROFILES = {
        EnhancementIntensity.SUBTLE: {
            "clahe_clip": 1.3,
            "warmth_b": 3.0,
            "warmth_a": 1.5,
            "saturation": 1.06,
            "contrast": 1.04,
            "sharpness_percent": 90,
        },
        EnhancementIntensity.BALANCED: {
            "clahe_clip": 1.85,
            "warmth_b": 5.5,
            "warmth_a": 2.5,
            "saturation": 1.14,
            "contrast": 1.08,
            "sharpness_percent": 135,
        },
        EnhancementIntensity.VIBRANT: {
            "clahe_clip": 2.4,
            "warmth_b": 8.0,
            "warmth_a": 4.0,
            "saturation": 1.22,
            "contrast": 1.13,
            "sharpness_percent": 170,
        },
    }

    @property
    def name(self) -> str:
        return "food_color_light_enhancement"

    def process(self, context: ImageContext) -> ImageContext:
        rgba = context.current_image.convert("RGBA")
        r, g, b, alpha = rgba.split()
        rgb_pil = Image.merge("RGB", (r, g, b))

        profile = self.INTENSITY_PROFILES[context.options.enhancement_intensity]
        rgb_np = np.array(rgb_pil)

        # 1. Conversão para CIE LAB para tratamento profissional de luminância e calor
        lab = cv2.cvtColor(rgb_np, cv2.COLOR_RGB2LAB)
        l_chan, a_chan, b_chan = cv2.split(lab)

        # Auto-ajuste adaptativo de exposição caso a foto original esteja muito escura
        mean_l = float(np.mean(l_chan))
        if mean_l < 110:
            gamma = max(0.72, mean_l / 135.0)
            inv_gamma = 1.0 / gamma
            table = np.array(
                [((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]
            ).astype("uint8")
            l_chan = cv2.LUT(l_chan, table)

        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=profile["clahe_clip"], tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l_chan)
        # Mescla 65% CLAHE + 35% L original para manter aspecto natural
        l_final = cv2.addWeighted(l_enhanced, 0.65, l_chan, 0.35, 0)

        # Aquecimento gastronômico (B+ = mais amarelo/dourado, A+ = mais vermelho/quente)
        a_final = np.clip(a_chan.astype(np.float32) + profile["warmth_a"], 0, 255).astype(np.uint8)
        b_final = np.clip(b_chan.astype(np.float32) + profile["warmth_b"], 0, 255).astype(np.uint8)

        enhanced_lab = cv2.merge((l_final, a_final, b_final))
        enhanced_rgb_np = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)
        enhanced_pil = Image.fromarray(enhanced_rgb_np, mode="RGB")

        # 2. Refinamento de Saturação e Contraste
        enhanced_pil = ImageEnhance.Color(enhanced_pil).enhance(profile["saturation"])
        enhanced_pil = ImageEnhance.Contrast(enhanced_pil).enhance(profile["contrast"])

        # 3. Filtro Unsharp Mask para nitidez de textura gastronômica
        enhanced_pil = enhanced_pil.filter(
            ImageFilter.UnsharpMask(
                radius=1.6,
                percent=int(profile["sharpness_percent"]),
                threshold=3,
            )
        )

        er, eg, eb = enhanced_pil.split()
        context.current_image = Image.merge("RGBA", (er, eg, eb, alpha))
        return context


class StudioFramingAndCompositionStep(PipelineStep):
    """
    Etapa 3: Centralização inteligente do alimento (Auto-Crop da bounding box do canal Alpha),
    padronização de resolução/proporção (ex: 1200x900 padrão iFood) e aplicação do fundo de estúdio
    com sombra de contato realista.
    """

    FRAMING_DIMENSIONS = {
        FramingPreset.IFOOD_STANDARD: (1200, 900),
        FramingPreset.SQUARE_CATALOG: (800, 800),
        FramingPreset.HD_SHOWCASE: (1280, 720),
    }

    @property
    def name(self) -> str:
        return "studio_framing_and_composition"

    def process(self, context: ImageContext) -> ImageContext:
        img_rgba = context.current_image.convert("RGBA")
        opts = context.options

        # Determina resolução final do canvas
        if opts.framing_preset == FramingPreset.ORIGINAL:
            target_w, target_h = img_rgba.size
        else:
            target_w, target_h = self.FRAMING_DIMENSIONS[opts.framing_preset]

        # Se o fundo foi removido, recorta a caixa delimitadora exata do prato para centralizar com precisão
        if opts.remove_background:
            alpha = np.array(img_rgba.split()[3])
            non_zero_y, non_zero_x = np.where(alpha > 20)
            if len(non_zero_y) > 10 and len(non_zero_x) > 10:
                bbox = (
                    int(np.min(non_zero_x)),
                    int(np.min(non_zero_y)),
                    int(np.max(non_zero_x)) + 1,
                    int(np.max(non_zero_y)) + 1,
                )
                subject = img_rgba.crop(bbox)
            else:
                subject = img_rgba

            # Redimensiona o prato respeitando a margem de respiro (padding_ratio) configurada
            usable_w = int(target_w * (1.0 - 2 * opts.padding_ratio))
            usable_h = int(target_h * (1.0 - 2 * opts.padding_ratio))

            scale = min(usable_w / max(1, subject.width), usable_h / max(1, subject.height))
            new_w = max(1, int(subject.width * scale))
            new_h = max(1, int(subject.height * scale))
            subject_resized = subject.resize((new_w, new_h), Image.Resampling.LANCZOS)

            paste_x = (target_w - new_w) // 2
            # Posiciona levemente abaixo do centro geométrico (52%) para equilíbrio visual de estúdio
            paste_y = int((target_h - new_h) * 0.54)

            if opts.background_preset == StudioBackgroundPreset.TRANSPARENT and not opts.custom_bg_hex:
                transparent_canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
                transparent_canvas.alpha_composite(subject_resized, dest=(paste_x, paste_y))
                context.current_image = transparent_canvas
            else:
                bg_canvas = studio_generator.generate_canvas(
                    width=target_w,
                    height=target_h,
                    preset=opts.background_preset,
                    custom_hex=opts.custom_bg_hex,
                )
                is_dark = opts.background_preset in (
                    StudioBackgroundPreset.DARK_SLATE,
                    StudioBackgroundPreset.RUSTIC_WOOD,
                )
                context.current_image = studio_generator.compose_with_contact_shadow(
                    background=bg_canvas,
                    subject_rgba=subject_resized,
                    paste_xy=(paste_x, paste_y),
                    add_shadow=opts.add_contact_shadow,
                    is_dark_bg=is_dark,
                )
        else:
            # Sem remoção de fundo: faz center-crop inteligente mantendo a proporção do preset
            context.current_image = self._smart_aspect_resize(img_rgba, target_w, target_h)

        context.metadata["final_dimensions"] = f"{target_w}x{target_h}"
        return context

    def _smart_aspect_resize(self, image: Image.Image, target_w: int, target_h: int) -> Image.Image:
        src_w, src_h = image.size
        target_ratio = target_w / target_h
        src_ratio = src_w / src_h

        if src_ratio > target_ratio:
            new_w = int(src_h * target_ratio)
            left = (src_w - new_w) // 2
            cropped = image.crop((left, 0, left + new_w, src_h))
        else:
            new_h = int(src_w / target_ratio)
            top = (src_h - new_h) // 2
            cropped = image.crop((0, top, src_w, top + new_h))

        return cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
