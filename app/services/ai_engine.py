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
        if self._session is not None:
            return

        start = time.perf_counter()
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
            self.engine_type = "opencv-grabcut-fallback"
            logger.warning(
                f"Não foi possível inicializar sessão ONNX/rembg ({exc}). "
                "Ativando motor de segmentação OpenCV GrabCut Salience como fallback."
            )

    @property
    def is_loaded(self) -> bool:
        return self._session is not None or self.engine_type == "opencv-grabcut-fallback"

    def remove_background(self, image: Image.Image) -> Image.Image:
        """
        Isola o alimento/prato removendo o fundo e retorna uma imagem PIL em modo RGBA
        com bordas suavizadas (alpha feathering).
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
                return self._refine_alpha_edges(result.convert("RGBA"))
            except Exception as exc:
                logger.warning(f"Falha na inferência rembg, utilizando fallback OpenCV: {exc}")

        return self._opencv_food_segmentation(image)

    def _refine_alpha_edges(self, rgba_image: Image.Image) -> Image.Image:
        """Aplica suavização morfológica leve no canal Alpha para eliminar serrilhados no contorno do prato."""
        arr = np.array(rgba_image)
        alpha = arr[:, :, 3]

        # Remove pequenos ruídos isolados fora do prato e suaviza a transição da borda
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        alpha_clean = cv2.morphologyEx(alpha, cv2.MORPH_OPEN, kernel, iterations=1)
        alpha_smooth = cv2.GaussianBlur(alpha_clean, (3, 3), 0)

        arr[:, :, 3] = alpha_smooth
        return Image.fromarray(arr, mode="RGBA")

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
