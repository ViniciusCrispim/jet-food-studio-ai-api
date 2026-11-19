import io
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
import pytest
from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def _generate_synthetic_food_image(width: int = 800, height: int = 600, dark: bool = False) -> bytes:
    """Cria uma imagem sintética simulando um prato de comida sobre uma mesa para testes de integração."""
    bg_color = (45, 40, 38) if dark else (140, 130, 120)
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Prato centralizado
    cx, cy = width // 2, height // 2
    draw.ellipse((cx - 220, cy - 160, cx + 220, cy + 160), fill=(230, 230, 235), outline=(200, 200, 210), width=4)
    # Alimento colorido no centro (hambúrguer/prato quente)
    draw.ellipse((cx - 140, cy - 110, cx + 140, cy + 110), fill=(185, 85, 35))
    draw.ellipse((cx - 95, cy - 75, cx + 95, cy + 75), fill=(225, 165, 35))
    draw.ellipse((cx - 50, cy - 40, cx + 50, cy + 40), fill=(65, 145, 55))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    return buf.read()


def test_health_check_endpoint(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Jet Food Studio IA"
    assert "ai_engine" in data
    assert "X-Process-Time-Ms" in response.headers


def test_photography_guide_endpoint(client: TestClient):
    response = client.get("/api/v1/guide")
    assert response.status_code == 200
    data = response.json()
    assert len(data["golden_rules"]) >= 4
    assert len(data["category_recommendations"]) >= 4
    assert len(data["checklist_before_upload"]) >= 4


def test_analyze_food_photo_endpoint(client: TestClient):
    img_bytes = _generate_synthetic_food_image(960, 720, dark=True)
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("prato_escuro.jpg", img_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert 0 <= data["overall_score"] <= 100
    assert data["dimensions"]["width"] == 960
    assert data["dimensions"]["height"] == 720
    assert len(data["metrics"]) == 5
    assert isinstance(data["recommendations"], list)


def test_studio_process_pipeline_endpoint(client: TestClient):
    img_bytes = _generate_synthetic_food_image(800, 600)
    response = client.post(
        "/api/v1/studio/process",
        files={"file": ("burger.jpg", img_bytes, "image/jpeg")},
        data={
            "remove_background": "true",
            "background_preset": "clean_studio",
            "enhancement_intensity": "balanced",
            "add_contact_shadow": "true",
            "framing_preset": "ifood_standard",
            "output_format": "WEBP",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["X-Studio-Final-Dimensions"] == "1200x900"
    assert "X-Studio-Step-Timings-Ms" in response.headers

    out_img = Image.open(io.BytesIO(response.content))
    assert out_img.size == (1200, 900)


def test_studio_compare_before_after_endpoint(client: TestClient):
    img_bytes = _generate_synthetic_food_image(640, 480, dark=True)
    response = client.post(
        "/api/v1/studio/compare",
        files={"file": ("pizza.jpg", img_bytes, "image/jpeg")},
        data={
            "background_preset": "rustic_wood",
            "framing_preset": "square_catalog",
            "enhancement_intensity": "vibrant",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["final_dimensions"] == "800x800"
    assert data["processed_image_data_url"].startswith("data:image/webp;base64,")
    assert "before_analysis" in data
    assert "after_analysis" in data


def test_reject_unsupported_file_type(client: TestClient):
    response = client.post(
        "/api/v1/analyze",
        files={"file": ("malicioso.txt", b"conteudo invalido", "text/plain")},
    )
    assert response.status_code == 415
    data = response.json()
    assert data["error"] is True
