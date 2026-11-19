from enum import Enum
from typing import List
from pydantic import BaseModel, Field


class QualityStatus(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"
    POOR = "POOR"


class MetricEvaluation(BaseModel):
    name: str = Field(..., description="Nome da métrica analisada")
    value: float = Field(..., description="Valor técnico medido")
    score: int = Field(..., ge=0, le=100, description="Nota normalizada de 0 a 100")
    status: str = Field(..., description="Classificação rápida (Ideal, Baixo, Alto, Crítico)")
    feedback: str = Field(..., description="Orientação prática em linguagem simples para o vendedor")


class ImageDimensions(BaseModel):
    width: int
    height: int
    aspect_ratio: str
    megapixels: float


class PhotoAnalysisResponse(BaseModel):
    overall_score: int = Field(..., ge=0, le=100, description="Nota geral de qualidade da foto (0 a 100)")
    status: QualityStatus = Field(..., description="Classificação geral da foto")
    ready_for_catalog: bool = Field(..., description="Indica se a foto tem qualidade suficiente para ir ao cardápio")
    summary: str = Field(..., description="Resumo executivo do diagnóstico para o restaurante")
    dimensions: ImageDimensions
    metrics: List[MetricEvaluation]
    recommendations: List[str] = Field(..., description="Lista acionável de melhorias para o vendedor")
    suggested_studio_params: dict = Field(..., description="Parâmetros recomendados para o endpoint de tratamento")
