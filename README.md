# 🍔 Jet Food Studio IA — Estúdio Fotográfico Inteligente para Plataformas de Delivery

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer_Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![ONNX Runtime](https://img.shields.io/badge/IS--Net_&_U²--Net-AI_Segmentation-FF6F00?style=for-the-badge)](https://onnxruntime.ai/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

> **Microsserviço de Visão Computacional e Inteligência Artificial** projetado para auxiliar restaurantes, lanchonetes e estabelecimentos gastronômicos a **padronizarem fotos reais de seus pratos** para plataformas de delivery, eliminando a necessidade de fotos meramente ilustrativas da internet ou de estúdios fotográficos de alto custo.

📖 **[Acesse aqui a Documentação Completa de Arquitetura & Engenharia (`docs/ARCHITECTURE.md`)](./docs/ARCHITECTURE.md)**

---

## 🎯 O Problema & A Proposta de Valor

Nas plataformas de delivery, pequenos e médios restaurantes enfrentam um obstáculo recorrente:
1. **Falta de capital ou de conhecimento técnico** para contratar fotógrafos especializados ou adquirir equipamentos de iluminação profissional;
2. Ao utilizar **fotos genéricas da internet**, o consumidor não sabe o que realmente está comprando, o que gera frustração, quebra de expectativa e avaliações negativas;
3. Ao publicar **fotos amadoras tiradas no balcão da cozinha**, o fundo poluído, as sombras duras e a iluminação inadequada tornam o prato menos atrativo, reduzindo a conversão de vendas.

### 💡 Como o Jet Food Studio IA soluciona esse cenário:
- **1. Guia Visual do Vendedor (`GET /api/v1/guide` + Diagramas SVG Interativos):** Orienta o restaurante sobre como fotografar com o próprio smartphone, apresentando diagramas visuais de ângulo (`45°` para pratos e hambúrgueres; `90°` zenital para pizzas), mapa de iluminação natural lateral e enquadramento correto da louça.
- **2. Diagnóstico Técnico da Foto (`POST /api/v1/analyze`):** Utiliza **Visão Computacional (OpenCV)** para avaliar a foto enviada pelo lojista com nota de `0 a 100` em cinco critérios (**Iluminação e Exposição**, **Nitidez e Foco via Variância do Laplaciano**, **Contraste Dinâmico**, **Vivacidade de Cores HSV** e **Resolução**), fornecendo recomendações práticas e diretas.
- **3. Padronização e Tratamento Gastronômico (`POST /api/v1/studio/process` & `/compare`):**
  - **Recorte de Alta Precisão com IA (`IS-Net / rembg` + Reconstrução Geométrica da Louça):** isola a refeição preservando a borda completa do prato para evitar o efeito de alimento flutuante;
  - **Realce Gastronômico no espaço de cor `CIE LAB`:** recupera detalhes nas sombras com **CLAHE**, aquece a temperatura das cores e destaca texturas com **Unsharp Mask**;
  - **Fundo de Estúdio Padronizado + Sombra de Contato Realista:** centraliza o prato nas dimensões ideais para cardápios digitais (`1200x900` na proporção `4:3`, `800x800` quadrado ou `1280x720` vitrine) e projeta sombra suave de contato na base do prato.
- **4. Playground Web Interativo (`GET /`):** Interface visual moderna com **comparador Antes vs. Depois (slider)**, gerador de foto de demonstração com um clique, relatório de diagnóstico e manual ilustrado para o vendedor.

---

## 🏗️ Arquitetura & Padrões de Projeto (Design Patterns)

O sistema foi desenvolvido aplicando **Clean Architecture** e padrões de projeto voltados para **alta performance, manutenibilidade e escalabilidade horizontal**:

```mermaid
flowchart LR
    Client["Cliente / API de PDV / Web Playground"] --> Router["API Layer (FastAPI v1)"]
    Router --> Pool["Async ThreadPool (Non-Blocking CPU)"]
    Pool --> Analyzer["Quality Analyzer (OpenCV)"]
    Pool --> Orchestrator["Pipeline Orchestrator"]

    subgraph Pipeline ["Pipeline Pattern (Chain of Responsibility)"]
        S1["1. BackgroundRemovalStep (Singleton IS-Net + Plate Recovery)"]
        S2["2. FoodColorAndLightEnhancementStep (CIE LAB CLAHE)"]
        S3["3. StudioFramingAndCompositionStep (Strategy Presets + Shadow)"]
        S1 --> S2 --> S3
    end

    Orchestrator --> Pipeline
```

| Padrão / Prática | Onde foi aplicado | Benefício de Engenharia |
| :--- | :--- | :--- |
| **Pipeline Pattern (Chain of Responsibility)** | `app/services/pipeline/` | Divide o processamento da imagem em etapas desacopladas (`PipelineStep`) que operam sobre um `ImageContext` e registram a latência individual por estágio. |
| **Singleton Pattern + Lifespan Warm-up** | `app/services/ai_engine.py` | Carrega a sessão neural `IS-Net` uma única vez na inicialização do servidor (`lifespan`), eliminando *cold-start* a cada requisição e contando com fallback automático em OpenCV GrabCut. |
| **Strategy Pattern** | `app/services/studio_generator.py` | Permite alternar dinamicamente entre estratégias de cenário (`clean_studio`, `warm_bistro`, `dark_slate`, `rustic_wood`, `transparent`) e de enquadramento (`delivery_standard`, `square_catalog`, `hd_showcase`). |
| **Application Factory & DTOs** | `app/main.py` & `app/schemas/` | Validação estrita de contratos de entrada e saída com **Pydantic v2** e gerenciamento de variáveis de ambiente com `pydantic-settings`. |
| **Non-Blocking CPU & In-Memory** | `app/api/v1/endpoints/` | Processamento matricial isolado em `run_in_threadpool` e manipulação de arquivos 100% em memória RAM (`io.BytesIO`), garantindo uma arquitetura *stateless* pronta para containers Docker e nuvem. |

---

## 📂 Estrutura de Diretórios

```text
jet-food-studio-ia/
├── app/
│   ├── main.py                      # Application Factory, Lifespan Warm-up, CORS e Middlewares
│   ├── core/
│   │   ├── config.py                # Configurações tipadas com Pydantic BaseSettings (.env)
│   │   ├── exceptions.py            # Exceções de domínio e Global Exception Handlers
│   │   └── logging.py               # Logging estruturado
│   ├── schemas/                     # Contratos de Dados (DTOs Pydantic v2)
│   │   ├── analysis.py              # Modelos do diagnóstico de qualidade (score, métricas)
│   │   ├── guide.py                 # Modelos do guia de fotografia para restaurantes
│   │   └── studio.py                # Enums de presets e opções do pipeline de estúdio
│   ├── api/
│   │   └── v1/
│   │       ├── dependencies.py      # Validação MIME, limite de tamanho, EXIF e normalização de resolução
│   │       ├── router.py            # Agregador de rotas /api/v1
│   │       └── endpoints/
│   │           ├── health.py        # GET /api/v1/health
│   │           ├── guide.py         # GET /api/v1/guide
│   │           ├── analyze.py       # POST /api/v1/analyze
│   │           └── studio.py        # POST /api/v1/studio/process e /api/v1/studio/compare
│   ├── services/
│   │   ├── ai_engine.py             # Singleton da sessão neural IS-Net (rembg) + Reconstrução de Louça
│   │   ├── quality_analyzer.py      # Diagnóstico técnico por Visão Computacional (OpenCV)
│   │   ├── studio_generator.py      # Geração procedural de fundos de estúdio e sombra de contato
│   │   └── pipeline/
│   │       ├── base.py              # Abstrações ImageContext e PipelineStep
│   │       ├── steps.py             # Etapas de Recorte, Realce CIE LAB e Enquadramento Delivery
│   │       └── orchestrator.py      # Orquestrador do pipeline e codificador de saída
│   └── static/
│       └── index.html               # Playground Web Interativo (Antes vs. Depois + Guia Visual SVG)
├── docs/
│   └── ARCHITECTURE.md              # Documentação aprofundada de arquitetura e algoritmos
├── tests/
│   └── test_api.py                  # Suíte de testes automatizados de integração (Pytest)
├── .env.example
├── .gitignore
├── Dockerfile
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## 📡 Referência de Endpoints

### 1. Playground Visual Interativo ("Antes e Depois" + Guia Visual)
- **Rota:** `GET /`
- Disponibiliza no navegador a interface interativa para upload de fotos reais (ou geração de foto de demonstração), comparador **Antes vs. Depois** com controle deslizante, notas de diagnóstico e manual visual ilustrado para o vendedor.

### 2. Healthcheck & Status do Motor de IA
- **Rota:** `GET /api/v1/health`
- **Resposta (`200 OK`):**
```json
{
  "status": "healthy",
  "service": "Jet Food Studio IA",
  "version": "1.0.0",
  "environment": "development",
  "ai_engine": {
    "loaded": true,
    "engine_type": "rembg-onnx (isnet-general-use)",
    "configured_model": "isnet-general-use",
    "warm_up_time_ms": 3317.34
  }
}
```

### 3. Guia de Fotografia para Restaurantes
- **Rota:** `GET /api/v1/guide`
- Retorna as **4 Regras de Ouro**, os requisitos de resolução, as recomendações de ângulo e iluminação por categoria (`Hambúrgueres`, `Pizzas`, `Pratos Executivos`, `Açaí & Sobremesas`) e o checklist pré-publicação.

### 4. Diagnóstico de Qualidade da Foto (Visão Computacional)
- **Rota:** `POST /api/v1/analyze` (`multipart/form-data` com o campo `file`)
- **Exemplo via cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -F "file=@meu_prato.jpg"
```
- **Resposta (`200 OK`):**
```json
{
  "overall_score": 74,
  "status": "GOOD",
  "ready_for_catalog": true,
  "summary": "Boa foto base! O pipeline de IA irá recortar o fundo e realçar a iluminação e textura do prato.",
  "dimensions": {
    "width": 960,
    "height": 720,
    "aspect_ratio": "4:3",
    "megapixels": 0.69
  },
  "metrics": [
    {
      "name": "Iluminação e Exposição",
      "value": 88.4,
      "score": 73,
      "status": "Levemente Escura",
      "feedback": "Foto um pouco subexposta. O tratamento automático irá clarear as sombras do prato."
    }
  ],
  "recommendations": [
    "Posicione o prato mais próximo a uma janela ou fonte de luz suave lateral (evite ambientes escuros)."
  ],
  "suggested_studio_params": {
    "remove_background": true,
    "preserve_plate_rim": true,
    "background_preset": "clean_studio",
    "enhancement_intensity": "balanced",
    "add_contact_shadow": true,
    "framing_preset": "delivery_standard"
  }
}
```

### 5. Processamento e Padronização da Foto (Retorno Binário para Catálogo / Storage S3)
- **Rota:** `POST /api/v1/studio/process` (`multipart/form-data`)
- **Parâmetros (`FormData`):**
  - `file`: Arquivo da imagem (`JPEG`, `PNG`, `WEBP`)
  - `remove_background`: `true` | `false` (padrão: `true`)
  - `preserve_plate_rim`: `true` | `false` (padrão: `true` — preserva e reconstrói a borda completa do prato)
  - `background_preset`: `clean_studio` | `warm_bistro` | `dark_slate` | `rustic_wood` | `transparent`
  - `enhancement_intensity`: `subtle` | `balanced` | `vibrant`
  - `add_contact_shadow`: `true` | `false` (padrão: `true`)
  - `framing_preset`: `delivery_standard` (`1200x900`) | `square_catalog` (`800x800`) | `hd_showcase` (`1280x720`) | `original`
  - `output_format`: `WEBP` | `JPEG` | `PNG`
- **Exemplo via cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/studio/process" \
  -F "file=@meu_prato.jpg" \
  -F "background_preset=clean_studio" \
  -F "framing_preset=delivery_standard" \
  -F "enhancement_intensity=balanced" \
  -F "preserve_plate_rim=true" \
  -F "output_format=WEBP" \
  --output prato_padronizado_delivery.webp
```

### 6. Comparativo Completo Antes vs. Depois (JSON + Base64)
- **Rota:** `POST /api/v1/studio/compare`
- Retorna o diagnóstico da foto original (`before_analysis`), o diagnóstico pós-tratamento (`after_analysis`), a telemetria de cada etapa do pipeline e a imagem final codificada em Data URL Base64 (`processed_image_data_url`).

---

## 🚀 Como Executar o Projeto Localmente

### Pré-requisitos
- **Python 3.10+**

### Passo a Passo
```bash
# 1. Acesse o diretório do projeto
cd c:\workspace\jet-food-studio-ia

# 2. Ative o ambiente virtual
.\.venv\Scripts\Activate.ps1

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Inicie o servidor FastAPI
uvicorn app.main:app --reload --port 8000
```

Acesse no seu navegador:
- 🖥️ **Estúdio Interativo (Antes & Depois + Guia Visual):** `http://localhost:8000/`
- 📄 **Documentação Interativa Swagger UI:** `http://localhost:8000/docs`

---

## 👨‍💻 Autor

**Vinícius Williams Crispim de Oliveira**  
- Graduando em Ciência da Computação (Estácio)  
- Bacharel em Direito (IESP)  
- [LinkedIn](https://www.linkedin.com/in/vinicius-crispim) · [GitHub](https://github.com/ViniciusCrispim)
