from typing import List
from pydantic import BaseModel, Field


class CategoryPhotoTip(BaseModel):
    category: str = Field(..., description="Categoria do alimento (ex: Hambúrgueres, Pizzas, Açaí & Sobremesas)")
    ideal_angle: str = Field(..., description="Ângulo recomendado da câmera")
    lighting_tip: str = Field(..., description="Dica específica de iluminação para o prato")
    staging_tip: str = Field(..., description="Como posicionar os ingredientes para valorizar o produto real")
    recommended_preset: str = Field(..., description="Preset de fundo do Jet Food Studio IA mais indicado")


class GoldenRule(BaseModel):
    title: str
    description: str
    do: str
    dont: str


class PhotographyGuideResponse(BaseModel):
    title: str
    purpose: str
    minimum_requirements: dict
    golden_rules: List[GoldenRule]
    category_recommendations: List[CategoryPhotoTip]
    checklist_before_upload: List[str]
