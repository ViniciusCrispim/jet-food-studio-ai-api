from typing import Optional, Tuple
import cv2
import numpy as np
from PIL import Image
from app.schemas.studio import StudioBackgroundPreset


class StudioBackgroundGenerator:
    """
    Strategy Pattern para geração procedural de fundos de estúdio fotográfico
    e projeção de sombra de contato realista na base do alimento/prato.
    """

    # Paletas estudadas para fotografia gastronômica (Topo, Centro/Luz, Base/Mesa)
    PRESET_PALETTES = {
        StudioBackgroundPreset.CLEAN_STUDIO: {
            "top": (244, 245, 247),
            "center": (253, 253, 254),
            "bottom": (232, 234, 238),
        },
        StudioBackgroundPreset.WARM_BISTRO: {
            "top": (246, 238, 226),
            "center": (253, 249, 242),
            "bottom": (229, 217, 200),
        },
        StudioBackgroundPreset.DARK_SLATE: {
            "top": (28, 31, 36),
            "center": (48, 53, 62),
            "bottom": (20, 22, 26),
        },
        StudioBackgroundPreset.RUSTIC_WOOD: {
            "top": (118, 82, 54),
            "center": (148, 106, 73),
            "bottom": (92, 62, 39),
        },
    }

    def generate_canvas(
        self,
        width: int,
        height: int,
        preset: StudioBackgroundPreset,
        custom_hex: Optional[str] = None,
    ) -> Image.Image:
        """Gera um fundo de estúdio com iluminação radial suave e linha sutil de superfície."""
        if custom_hex:
            base_rgb = self._parse_hex_color(custom_hex)
            palette = {
                "top": tuple(max(0, int(c * 0.94)) for c in base_rgb),
                "center": tuple(min(255, int(c * 1.03)) for c in base_rgb),
                "bottom": tuple(max(0, int(c * 0.88)) for c in base_rgb),
            }
        else:
            palette = self.PRESET_PALETTES.get(
                preset, self.PRESET_PALETTES[StudioBackgroundPreset.CLEAN_STUDIO]
            )

        # Cria gradiente vertical suave (parede de fundo -> superfície da mesa em 68% da altura)
        y_norm = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None]
        horizon = 0.68

        top = np.array(palette["top"], dtype=np.float32)
        center = np.array(palette["center"], dtype=np.float32)
        bottom = np.array(palette["bottom"], dtype=np.float32)

        canvas = np.zeros((height, width, 3), dtype=np.float32)

        upper_mask = (y_norm <= horizon).flatten()
        lower_mask = ~upper_mask

        t_upper = (y_norm[upper_mask] / horizon)[:, :, None]
        canvas[upper_mask] = top * (1.0 - t_upper) + center * t_upper

        t_lower = ((y_norm[lower_mask] - horizon) / (1.0 - horizon))[:, :, None]
        canvas[lower_mask] = center * (1.0 - t_lower) + bottom * t_lower

        # Adiciona iluminação radial de estúdio (softbox centralizado levemente acima do prato)
        x = np.linspace(-1.0, 1.0, width, dtype=np.float32)[None, :]
        y = np.linspace(-1.0, 1.0, height, dtype=np.float32)[:, None]
        radial_dist = np.sqrt((x * 0.85) ** 2 + ((y - 0.05) * 0.95) ** 2)
        spotlight = np.clip(1.0 - (radial_dist ** 1.8) * 0.14, 0.84, 1.04)[:, :, None]

        canvas = np.clip(canvas * spotlight, 0, 255).astype(np.uint8)
        return Image.fromarray(canvas, mode="RGB").convert("RGBA")

    def compose_with_contact_shadow(
        self,
        background: Image.Image,
        subject_rgba: Image.Image,
        paste_xy: Tuple[int, int],
        add_shadow: bool = True,
        is_dark_bg: bool = False,
    ) -> Image.Image:
        """
        Compõe o alimento recortado sobre o fundo de estúdio, projetando uma
        sombra elíptica suave de contato na base do prato para evitar efeito 'colagem'.
        """
        canvas = background.copy().convert("RGBA")
        if not add_shadow:
            canvas.alpha_composite(subject_rgba, dest=paste_xy)
            return canvas

        alpha = np.array(subject_rgba.split()[3])
        non_zero_y, non_zero_x = np.where(alpha > 25)

        if len(non_zero_y) > 0:
            min_x, max_x = int(np.min(non_zero_x)), int(np.max(non_zero_x))
            max_y = int(np.max(non_zero_y))

            subj_w = max(20, max_x - min_x)
            subj_h = subject_rgba.height

            shadow_layer = np.zeros((canvas.height, canvas.width, 4), dtype=np.uint8)

            center_x = paste_xy[0] + min_x + subj_w // 2
            center_y = min(canvas.height - 6, paste_xy[1] + max_y - max(3, int(subj_h * 0.03)))

            axis_x = max(15, int(subj_w * 0.44))
            axis_y = max(6, int(subj_h * 0.075))

            shadow_alpha = np.zeros((canvas.height, canvas.width), dtype=np.uint8)
            base_opacity = 135 if not is_dark_bg else 185
            cv2.ellipse(
                shadow_alpha,
                (center_x, center_y),
                (axis_x, axis_y),
                0,
                0,
                360,
                base_opacity,
                -1,
            )

            blur_k = max(21, (int(axis_x * 0.45) // 2) * 2 + 1)
            shadow_alpha = cv2.GaussianBlur(shadow_alpha, (blur_k, blur_k), 0)

            # Cor da sombra levemente quente/escura para harmonia visual
            shadow_layer[:, :, 0] = 18
            shadow_layer[:, :, 1] = 16
            shadow_layer[:, :, 2] = 15
            shadow_layer[:, :, 3] = shadow_alpha

            shadow_pil = Image.fromarray(shadow_layer, mode="RGBA")
            canvas = Image.alpha_composite(canvas, shadow_pil)

        canvas.alpha_composite(subject_rgba, dest=paste_xy)
        return canvas

    def _parse_hex_color(self, hex_str: str) -> Tuple[int, int, int]:
        cleaned = hex_str.strip().lstrip("#")
        if len(cleaned) == 3:
            cleaned = "".join(c * 2 for c in cleaned)
        if len(cleaned) != 6:
            return (248, 248, 250)
        try:
            return (
                int(cleaned[0:2], 16),
                int(cleaned[2:4], 16),
                int(cleaned[4:6], 16),
            )
        except ValueError:
            return (248, 248, 250)


studio_generator = StudioBackgroundGenerator()
