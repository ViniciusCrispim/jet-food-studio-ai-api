from math import gcd
import cv2
import numpy as np
from PIL import Image
from app.schemas.analysis import (
    ImageDimensions,
    MetricEvaluation,
    PhotoAnalysisResponse,
    QualityStatus,
)


class FoodPhotoQualityAnalyzer:
    """
    Motor de Visão Computacional para diagnóstico técnico de fotos gastronômicas.
    Avalia Iluminação/Exposição, Nitidez (Laplacian Variance), Contraste,
    Saturação/Apetitosidade e Resolução antes ou durante a publicação no cardápio.
    """

    def analyze(self, image: Image.Image) -> PhotoAnalysisResponse:
        rgb = np.array(image.convert("RGB"))
        h, w = rgb.shape[:2]
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)

        # 1. Avaliação de Iluminação / Exposição (Média de Luminância 0-255)
        mean_brightness = float(np.mean(gray))
        brightness_metric, brightness_rec = self._evaluate_brightness(mean_brightness)

        # 2. Avaliação de Nitidez / Foco (Variância do Operador Laplaciano)
        # Normaliza resolução para cálculo consistente de foco
        norm_scale = min(1.0, 800.0 / max(h, w))
        norm_gray = (
            cv2.resize(gray, (int(w * norm_scale), int(h * norm_scale)))
            if norm_scale < 1.0
            else gray
        )
        sharpness_val = float(cv2.Laplacian(norm_gray, cv2.CV_64F).var())
        sharpness_metric, sharpness_rec = self._evaluate_sharpness(sharpness_val)

        # 3. Avaliação de Contraste (Desvio Padrão da Luminância)
        contrast_val = float(np.std(gray))
        contrast_metric, contrast_rec = self._evaluate_contrast(contrast_val)

        # 4. Avaliação de Vivacidade / Cores Gastronômicas (Canal S do HSV)
        saturation_val = float(np.mean(hsv[:, :, 1]))
        saturation_metric, saturation_rec = self._evaluate_saturation(saturation_val)

        # 5. Avaliação de Resolução para Cardápio de Delivery
        resolution_metric, resolution_rec = self._evaluate_resolution(w, h)

        metrics = [
            brightness_metric,
            sharpness_metric,
            contrast_metric,
            saturation_metric,
            resolution_metric,
        ]

        # Média ponderada das notas (Iluminação e Nitidez têm maior peso na conversão de vendas)
        weights = [0.28, 0.27, 0.15, 0.15, 0.15]
        overall_score = int(round(sum(m.score * weight for m, weight in zip(metrics, weights))))

        recommendations = [
            rec
            for rec in [
                brightness_rec,
                sharpness_rec,
                contrast_rec,
                saturation_rec,
                resolution_rec,
            ]
            if rec
        ]

        if not recommendations:
            recommendations.append(
                "Excelente captura! A foto possui boa iluminação, foco nítido e resolução ideal para cardápios de delivery."
            )

        status, summary = self._classify_overall(overall_score)
        suggested_intensity = "vibrant" if overall_score < 68 else ("balanced" if overall_score < 85 else "subtle")

        divisor = gcd(w, h) or 1
        aspect_ratio = f"{w // divisor}:{h // divisor}"

        return PhotoAnalysisResponse(
            overall_score=overall_score,
            status=status,
            ready_for_catalog=overall_score >= 55,
            summary=summary,
            dimensions=ImageDimensions(
                width=w,
                height=h,
                aspect_ratio=aspect_ratio,
                megapixels=round((w * h) / 1_000_000, 2),
            ),
            metrics=metrics,
            recommendations=recommendations,
            suggested_studio_params={
                "remove_background": True,
                "preserve_plate_rim": True,
                "background_preset": "clean_studio",
                "enhancement_intensity": suggested_intensity,
                "add_contact_shadow": True,
                "framing_preset": "delivery_standard",
            },
        )

    def _evaluate_brightness(self, val: float) -> tuple[MetricEvaluation, str | None]:
        # Faixa ideal de brilho médio para fotos de comida: 105 a 175
        if 105 <= val <= 175:
            score = 95
            status = "Ideal"
            feedback = "Iluminação bem equilibrada, destacando os detalhes do prato sem sombras pesadas."
            rec = None
        elif 75 <= val < 105:
            score = int(60 + (val - 75))
            status = "Levemente Escura"
            feedback = "Foto um pouco subexposta. O tratamento automático irá clarear as sombras do prato."
            rec = "Posicione o prato mais próximo a uma janela ou fonte de luz suave lateral (evite ambientes escuros)."
        elif val < 75:
            score = max(20, int(val * 0.75))
            status = "Muito Escura"
            feedback = "Baixa luminosidade detectada, o que esconde a textura real da comida."
            rec = "A foto está muito escura. Fotografe em um local bem iluminado (preferencialmente luz natural do dia) ou use o modo 'Vibrant' no estúdio."
        elif 175 < val <= 205:
            score = int(85 - (val - 175))
            status = "Levemente Clara"
            feedback = "Iluminação intensa, mas ainda dentro de uma margem recuperável."
            rec = "Evite usar o flash direto do celular em cima do prato para não criar reflexos estourados."
        else:
            score = max(30, int(100 - (val - 175)))
            status = "Superexposta"
            feedback = "Excesso de luz (possível flash direto ou fundo estourado)."
            rec = "Desligue o flash direto e afaste levemente a fonte de luz para preservar as cores naturais dos ingredientes."

        return (
            MetricEvaluation(
                name="Iluminação e Exposição",
                value=round(val, 1),
                score=min(100, max(0, score)),
                status=status,
                feedback=feedback,
            ),
            rec,
        )

    def _evaluate_sharpness(self, val: float) -> tuple[MetricEvaluation, str | None]:
        if val >= 140:
            score = min(100, int(85 + min(15, (val - 140) / 25)))
            status = "Nítida"
            feedback = "Ótimo foco! As texturas dos ingredientes estão bem definidas."
            rec = None
        elif 65 <= val < 140:
            score = int(60 + ((val - 65) / 75) * 24)
            status = "Aceitável"
            feedback = "Foco moderado. O filtro de nitidez do estúdio ajudará a realçar as texturas."
            rec = "Antes de clicar, toque na tela do celular exatamente sobre o prato e limpe a lente da câmera."
        else:
            score = max(20, int((val / 65) * 55))
            status = "Desfocada / Tremida"
            feedback = "A imagem apresenta baixa nitidez ou movimento durante o clique."
            rec = "A foto parece desfocada ou tremida. Apoie os cotovelos na mesa ao fotografar e mantenha cerca de 30cm a 50cm de distância do prato."

        return (
            MetricEvaluation(
                name="Nitidez e Foco",
                value=round(val, 1),
                score=min(100, max(0, score)),
                status=status,
                feedback=feedback,
            ),
            rec,
        )

    def _evaluate_contrast(self, val: float) -> tuple[MetricEvaluation, str | None]:
        if 42 <= val <= 82:
            score = 92
            status = "Equilibrado"
            feedback = "Bom alcance dinâmico entre luzes e sombras."
            rec = None
        elif val < 42:
            score = max(35, int((val / 42) * 75))
            status = "Baixo Contraste"
            feedback = "Imagem com aparência 'lavada' ou opaca."
            rec = "Use um fundo neutro que contraste com a cor do prato para destacar melhor o alimento."
        else:
            score = max(55, int(90 - (val - 82) * 0.6))
            status = "Alto Contraste"
            feedback = "Sombras marcadas detectadas."
            rec = "Use uma folha branca ou cortina fina para difundir a luz e suavizar sombras duras."

        return (
            MetricEvaluation(
                name="Contraste Dinâmico",
                value=round(val, 1),
                score=min(100, max(0, score)),
                status=status,
                feedback=feedback,
            ),
            rec,
        )

    def _evaluate_saturation(self, val: float) -> tuple[MetricEvaluation, str | None]:
        if 55 <= val <= 165:
            score = 92
            status = "Apetitosa"
            feedback = "Cores vivas e naturais que estimulam o apetite."
            rec = None
        elif val < 55:
            score = max(40, int((val / 55) * 75))
            status = "Cores Pálidas"
            feedback = "As cores do prato estão pouco vibrantes. O realce gastronômico aquecerá os tons."
            rec = "Inclua elementos frescos de cor no prato (ex: ervas frescas, tomate, molho brilhante) e evite luz fluorescente muito branca/azulada."
        else:
            score = 72
            status = "Muito Saturada"
            feedback = "Cores bastante intensas."
            rec = "Evite aplicar filtros exagerados de redes sociais antes de enviar a foto para o cardápio."

        return (
            MetricEvaluation(
                name="Vivacidade de Cores",
                value=round(val, 1),
                score=min(100, max(0, score)),
                status=status,
                feedback=feedback,
            ),
            rec,
        )

    def _evaluate_resolution(self, width: int, height: int) -> tuple[MetricEvaluation, str | None]:
        min_side = min(width, height)
        if width >= 1000 and height >= 750:
            score = 98
            status = "Alta Definição"
            feedback = f"Resolução excelente ({width}x{height}px) para plataformas de delivery."
            rec = None
        elif min_side >= 500:
            score = 78
            status = "Adequada"
            feedback = f"Resolução aceitável ({width}x{height}px). Será padronizada pelo estúdio."
            rec = "Para máxima nitidez no zoom do cliente, fotografe com a câmera traseira na resolução original (evite fotos baixadas do WhatsApp)."
        else:
            score = 45
            status = "Baixa Resolução"
            feedback = f"Imagem pequena ({width}x{height}px), podendo perder qualidade em telas maiores."
            rec = "Evite tirar print da tela ou usar miniaturas. Envie a foto original tirada pela câmera do celular (mínimo recomendado: 800x600px)."

        return (
            MetricEvaluation(
                name="Resolução para Cardápio",
                value=float(width * height),
                score=score,
                status=status,
                feedback=feedback,
            ),
            rec,
        )

    def _classify_overall(self, score: int) -> tuple[QualityStatus, str]:
        if score >= 85:
            return (
                QualityStatus.EXCELLENT,
                "Foto de excelente qualidade! Pronta para receber o fundo padronizado de estúdio.",
            )
        if score >= 70:
            return (
                QualityStatus.GOOD,
                "Boa foto base! O pipeline de IA irá recortar o fundo e realçar a iluminação e textura do prato.",
            )
        if score >= 55:
            return (
                QualityStatus.NEEDS_IMPROVEMENT,
                "Foto utilizável, mas com pontos de atenção na luz ou nitidez. Recomendamos aplicar o tratamento no modo 'Balanced' ou 'Vibrant'.",
            )
        return (
            QualityStatus.POOR,
            "A foto apresenta limitações importantes de iluminação ou foco. Nosso estúdio aplicará recuperação máxima, mas considere seguir as dicas abaixo para uma nova captura.",
        )


quality_analyzer = FoodPhotoQualityAnalyzer()
