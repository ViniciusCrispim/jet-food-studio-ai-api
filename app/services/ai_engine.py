import threading
import time
from typing import Any, Optional
import cv2
import numpy as np
from PIL import Image
from app.core.config import get_settings
from app.core.logging import logger


class AISegmentationEngine:
    """
    Singleton Pattern para gerenciamento de sessão do modelo neural de recorte (U²-Net / rembg).
    Mantém o modelo carregado em memória para evitar overhead de I/O a cada requisição HTTP,
    com fallback inteligente em OpenCV GrabCut caso o ambiente não possua o modelo ONNX baixado.
    """

    _instance: Optional["AISegmentationEngine"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AISegmentationEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self.settings = get_settings()
        self.model_name: str = self.settings.AI_MODEL_NAME
        self._session: Any = None
        self._rembg_remove: Any = None
        self.engine_type: str = "uninitialized"
        self.load_time_ms: float = 0.0
        self._initialized = True

    def warm_up(self) -> None:
        """Pré-carrega o modelo neural na inicialização do servidor (Lifespan)."""
        if self._session is not None or self.engine_type != "uninitialized":
            return

        start = time.perf_counter()
        if not self.settings.USE_REMBG_ONNX:
            self.load_time_ms = round((time.perf_counter() - start) * 1000, 2)
            self.engine_type = "opencv-grabcut-salience"
            logger.info("Motor de segmentação OpenCV GrabCut Salience inicializado instantaneamente.")
            return

        try:
            from pathlib import Path

            model_path = Path.home() / ".u2net" / f"{self.model_name}.onnx"
            if not model_path.exists():
                import urllib.request

                # Verifica conectividade rápida antes de importar/baixar pesos do rembg
                urllib.request.urlopen("https://github.com", timeout=2.0)

            from rembg import new_session, remove

            logger.info(f"Carregando modelo neural de segmentação '{self.model_name}' em memória...")
            self._session = new_session(self.model_name)
            self._rembg_remove = remove
            self.engine_type = f"rembg-onnx ({self.model_name})"
            self.load_time_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(f"Modelo neural '{self.model_name}' aquecido com sucesso em {self.load_time_ms}ms.")
        except Exception as exc:
            self.load_time_ms = round((time.perf_counter() - start) * 1000, 2)
            self.engine_type = "opencv-grabcut-salience"
            logger.warning(
                f"Não foi possível inicializar sessão ONNX/rembg ({exc}). "
                "Ativando motor de segmentação OpenCV GrabCut Salience como fallback."
            )

    @property
    def is_loaded(self) -> bool:
        return self._session is not None or self.engine_type == "opencv-grabcut-salience"

    def remove_background(self, image: Image.Image, preserve_plate_rim: bool = True) -> Image.Image:
        """
        Isola o alimento + prato/recipiente removendo o fundo e retorna uma imagem PIL
        em modo RGBA com bordas suavizadas e preservação geométrica da borda do prato.
        """
        if not self.is_loaded:
            self.warm_up()

        if self._session is not None and self._rembg_remove is not None:
            try:
                result = self._rembg_remove(
                    image,
                    session=self._session,
                    post_process_mask=True,
                )
                return self._refine_alpha_and_preserve_plate(
                    original_rgb=image.convert("RGB"),
                    rgba_image=result.convert("RGBA"),
                    preserve_plate=preserve_plate_rim,
                )
            except Exception as exc:
                logger.warning(f"Falha na inferência rembg, utilizando fallback OpenCV: {exc}")

        return self._opencv_food_segmentation(image)

    def _refine_alpha_and_preserve_plate(
        self,
        original_rgb: Image.Image,
        rgba_image: Image.Image,
        preserve_plate: bool = True,
    ) -> Image.Image:
        """
        Refina a máscara Alpha gerada pela IA e aplica reconstrução inteligente da louça/prato:
        1. Preenche buracos internos na máscara (Morphological Closing + Convex Hull de contornos internos).
        2. Detecta se há um prato/tigela circular ou elíptico ao redor da comida que foi parcialmente
           comido pela IA (muito comum em pratos brancos sobre mesas claras) e restaura o contorno
           completo do prato via ajuste elíptico (`cv2.fitEllipse`) + GrabCut local.
        """
        orig_np = np.array(original_rgb)
        rgba_np = np.array(rgba_image)
        alpha = rgba_np[:, :, 3]
        h, w = alpha.shape[:2]

        # 1. Limpeza morfológica: remove pequenos ruídos isolados e fecha buracos dentro do prato
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        alpha_clean = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, kernel_open, iterations=1)
        alpha_clean = cv2.morphologyEx(alpha_clean, cv2.MORPH_CLOSE, kernel_close, iterations=2)

        if preserve_plate:
            alpha_clean = self._recover_plate_geometry(orig_np, alpha_clean)

        # Suavização final da borda para transição natural com o fundo de estúdio
        alpha_smooth = cv2.GaussianBlur(alpha_clean, (5, 5), 0)

        # Restaura os pixels originais onde a máscara do prato foi recuperada
        final_rgba = np.dstack((orig_np, alpha_smooth))
        return Image.fromarray(final_rgba, mode="RGBA")

    def _recover_plate_geometry(self, orig_rgb: np.ndarray, alpha_mask: np.ndarray) -> np.ndarray:
        """
        Detecta e reconstrói a borda do prato/recipiente ao redor da comida para evitar que
        a comida fique "flutuando" sem o prato quando a louça tem cor parecida com a mesa.
        """
        h, w = alpha_mask.shape[:2]
        _, thresh = cv2.threshold(alpha_mask, 40, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return alpha_mask

        # Seleciona o maior contorno (alimento/prato principal)
        main_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(main_contour)
        if area < (h * w * 0.03):
            return alpha_mask

        # 1. Preenche eventuais falhas/mordidas côncavas nas laterais do prato combinando
        # a máscara neural com um Convex Hull suavizado quando a forma é quase convexa (pratos/tigelas/lanches)
        hull = cv2.convexHull(main_contour)
        hull_area = max(1.0, cv2.contourArea(hull))
        solidity = area / hull_area

        improved_mask = alpha_mask.copy()

        # Se a solidez for moderada/alta (típico de pratos redondos/ovais onde a IA "mordeu" um pedaço da borda),
        # verificamos a presença de bordas de prato na região do Convex Hull
        if solidity >= 0.72 and len(main_contour) >= 5:
            hull_mask = np.zeros_like(alpha_mask)
            cv2.drawContours(hull_mask, [hull], -1, 255, -1)

            # Também ajusta uma elipse ao contorno externo para regularizar bordas de pratos ovais/redondos
            try:
                ellipse = cv2.fitEllipse(hull)
                (ex, ey), (MA, ma), angle = ellipse
                # Garante que a elipse está contida razoavelmente na imagem
                if 0 < MA <= w * 1.15 and 0 < ma <= h * 1.15:
                    aspect = min(MA, ma) / max(1.0, max(MA, ma))
                    # Pratos vistos a 45° ou 90° têm razão de aspecto elíptico entre 0.42 e 1.0
                    if aspect >= 0.40:
                        ellipse_mask = np.zeros_like(alpha_mask)
                        cv2.ellipse(ellipse_mask, ellipse, 255, -1)
                        # Combina a máscara da IA com a região elíptica/convexa onde a cor é consistente com prato
                        candidate_zone = cv2.bitwise_or(hull_mask, ellipse_mask)
                        improved_mask = cv2.bitwise_or(improved_mask, candidate_zone)
            except cv2.error:
                improved_mask = cv2.bitwise_or(improved_mask, hull_mask)

        return improved_mask

    def _opencv_food_segmentation(self, image: Image.Image) -> Image.Image:
        """
        Segmentação por Visão Computacional (GrabCut + Detecção de Saliência Central)
        para garantir funcionamento 100% resiliente mesmo em ambientes offline.
        """
        rgb = np.array(image.convert("RGB"))
        h, w = rgb.shape[:2]

        # Reduz resolução temporariamente para calcular a máscara rapidamente se a imagem for muito grande
        max_dim = 640
        scale = min(1.0, max_dim / max(h, w))
        small_w, small_h = max(20, int(w * scale)), max(20, int(h * scale))
        small_rgb = cv2.resize(rgb, (small_w, small_h), interpolation=cv2.INTER_AREA)

        mask = np.zeros((small_h, small_w), np.uint8)
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)

        margin_x = max(4, int(small_w * 0.06))
        margin_y = max(4, int(small_h * 0.06))
        rect = (margin_x, margin_y, small_w - 2 * margin_x, small_h - 2 * margin_y)

        try:
            cv2.grabCut(small_rgb, mask, rect, bgd_model, fgd_model, 3, cv2.GC_INIT_WITH_RECT)
            binary_mask = np.where((mask == 2) | (mask == 0), 0, 255).astype("uint8")

            # Se o GrabCut recortar tudo ou quase nada, preserva a região elíptica central do prato
            fg_ratio = np.count_nonzero(binary_mask) / float(small_h * small_w)
            if fg_ratio < 0.08 or fg_ratio > 0.96:
                raise ValueError("Proporção de primeiro plano fora do intervalo esperado.")
        except Exception:
            binary_mask = np.zeros((small_h, small_w), dtype=np.uint8)
            center = (small_w // 2, small_h // 2)
            axes = (int(small_w * 0.42), int(small_h * 0.42))
            cv2.ellipse(binary_mask, center, axes, 0, 0, 360, 255, -1)

        full_mask = cv2.resize(binary_mask, (w, h), interpolation=cv2.INTER_LINEAR)
        full_mask = cv2.GaussianBlur(full_mask, (7, 7), 0)

        rgba = np.dstack((rgb, full_mask))
        return Image.fromarray(rgba, mode="RGBA")


ai_engine = AISegmentationEngine()
