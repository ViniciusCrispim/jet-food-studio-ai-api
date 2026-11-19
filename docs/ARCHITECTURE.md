# 🏛️ Documentação de Arquitetura & Engenharia — Jet Food Studio IA

Este documento detalha as decisões arquiteturais, os **Design Patterns (Padrões de Projeto)**, os algoritmos de **Visão Computacional / IA** e as estratégias de **Escalabilidade e Concorrência** aplicadas na construção do microsserviço **Jet Food Studio IA**.

---

## 1. Visão Geral da Arquitetura (Clean & Layered Architecture)

A aplicação foi estruturada sob os princípios de **Clean Architecture** e **Separation of Concerns (SoC)**, dividindo responsabilidades em 4 camadas bem definidas e desacopladas:

```mermaid
flowchart TB
    subgraph Presentation ["1. Presentation & API Layer (app/api/v1 & app/static)"]
        UI["Playground Web Interativo (index.html)"]
        H["GET /api/v1/health"]
        G["GET /api/v1/guide"]
        A["POST /api/v1/analyze"]
        S["POST /api/v1/studio/process & /compare"]
        DEP["Dependencies: Validação MIME, Tamanho & EXIF Transpose"]
    end

    subgraph Contracts ["2. Domain Contracts / DTOs (app/schemas)"]
        SC_G["PhotographyGuideResponse"]
        SC_A["PhotoAnalysisResponse & MetricEvaluation"]
        SC_S["StudioProcessOptions & Enums"]
    end

    subgraph DomainServices ["3. Core Services & Pipeline Layer (app/services)"]
        QA["FoodPhotoQualityAnalyzer (OpenCV)"]
        ORCH["FoodStudioPipelineOrchestrator"]
        AI["AISegmentationEngine (Singleton U²-Net / GrabCut)"]
        BG["StudioBackgroundGenerator (Strategy Pattern)"]
    end

    subgraph Infrastructure ["4. Core & Cross-Cutting (app/core)"]
        CFG["Settings (Pydantic BaseSettings)"]
        EXC["Global Exception Handlers"]
        LOG["Structured Logging & X-Process-Time-Ms Middleware"]
    end

    UI --> G & A & S
    A & S --> DEP
    G --> SC_G
    A --> QA --> SC_A
    S --> ORCH --> SC_S
    ORCH --> AI & BG
```

---

## 2. Padrões de Projeto (Design Patterns) Implementados

### 2.1. Pipeline Pattern / Chain of Responsibility (`app/services/pipeline/`)
Para evitar uma função monolítica difícil de dar manutenção ou testar, o tratamento da imagem foi modelado como um **Pipeline de estágios independentes**:

1. **`ImageContext` ([base.py](file:///c:/workspace/jet-food-studio-ia/app/services/pipeline/base.py)):** Objeto de contexto que carrega a imagem original, a imagem em transformação (`current_image`), as opções solicitadas (`StudioProcessOptions`) e um dicionário de telemetria (`step_timings_ms`).
2. **`PipelineStep` ([base.py](file:///c:/workspace/jet-food-studio-ia/app/services/pipeline/base.py)):** Classe base abstrata (`ABC`) que exige que toda etapa implemente `name` e `process(context) -> ImageContext`.
3. **Etapas Concretas ([steps.py](file:///c:/workspace/jet-food-studio-ia/app/services/pipeline/steps.py)):**
   - `BackgroundRemovalStep`: Isola o prato/alimento removendo o fundo e aplicando suavização morfológica (*alpha feathering*) nas bordas.
   - `FoodColorAndLightEnhancementStep`: Realça luz, calor e nitidez especificamente para fotografia de alimentos.
   - `StudioFramingAndCompositionStep`: Recorta a caixa delimitadora (*bounding box*) do alimento, centraliza na proporção de delivery escolhida e compõe sobre o fundo de estúdio com sombra de contato.
4. **`FoodStudioPipelineOrchestrator` ([orchestrator.py](file:///c:/workspace/jet-food-studio-ia/app/services/pipeline/orchestrator.py)):** Executa a cadeia sequencialmente, cronometra o tempo exato (em `ms`) de cada etapa e codifica a saída final em memória (`WEBP`, `JPEG` ou `PNG`).

### 2.2. Singleton Pattern + Lifespan Warm-up (`app/services/ai_engine.py`)
Redes neurais de segmentação como a **U²-Net (`rembg` / `ONNX Runtime`)** possuem dezenas de megabytes de pesos. Se o modelo fosse instanciado a cada requisição HTTP:
- Haveria alto consumo de RAM e I/O de disco;
- A latência por requisição subiria para mais de 4 a 6 segundos.

**Solução adotada:**
- A classe `AISegmentationEngine` implementa um **Singleton Thread-Safe** (`threading.Lock`).
- Durante o evento `lifespan` de inicialização do FastAPI ([main.py](file:///c:/workspace/jet-food-studio-ia/app/main.py)), o método `ai_engine.warm_up()` pré-carrega a sessão `new_session("u2netp")` uma única vez na memória RAM.
- **Fallback Resiliente (Circuit Breaker Local):** Caso o servidor esteja rodando em ambiente sem GPU/ONNX ou offline sem os pesos baixados, o motor aciona automaticamente o algoritmo de visão computacional **OpenCV GrabCut + Salience Mask**, garantindo disponibilidade de 100% sem quebrar a requisição.

### 2.3. Strategy Pattern (`app/services/studio_generator.py` & `app/schemas/studio.py`)
Tanto a geração do cenário de fundo quanto o enquadramento funcionam como estratégias intercambiáveis selecionadas via parâmetros tipados:
- **Estratégias de Fundo (`StudioBackgroundPreset`):**
  - `clean_studio`: Gradiente branco/off-white com iluminação radial *softbox* (padrão iFood).
  - `warm_bistro`: Tons creme quentes para padarias, doces, açaí e massas.
  - `dark_slate`: Ardósia escura gourmet para hambúrgueres artesanais, carnes e culinária oriental.
  - `rustic_wood`: Paleta amadeirada quente para pizzas e porções.
  - `transparent`: Mantém o canal Alpha 100% transparente.
- **Estratégias de Enquadramento (`FramingPreset`):**
  - `ifood_standard` (`1200x900` — proporção `4:3` oficial do iFood).
  - `square_catalog` (`800x800` — proporção `1:1`).
  - `hd_showcase` (`1280x720` — proporção `16:9`).
  - `original` (preserva dimensões nativas).

### 2.4. Application Factory & Dependency Injection (`app/main.py` & `app/api/v1/dependencies.py`)
- `create_application()` encapsula a criação da instância FastAPI, middlewares de CORS, telemetria de tempo e registro de handlers globais de exceção.
- `validate_and_load_image()` atua como validador reutilizável de entrada: checa `Content-Type`, bloqueia arquivos acima de `MAX_UPLOAD_SIZE_MB` (HTTP `413`), rejeita formatos inválidos (HTTP `415`) e aplica `ImageOps.exif_transpose` para corrigir fotos de celulares tiradas de cabeça para baixo ou rotacionadas.

---

## 3. Algoritmos de Visão Computacional & Tratamento Gastronômico

### 3.1. Diagnóstico Técnico da Foto (`FoodPhotoQualityAnalyzer`)
Localizado em [quality_analyzer.py](file:///c:/workspace/jet-food-studio-ia/app/services/quality_analyzer.py), avalia 5 dimensões matemáticas da imagem e gera uma nota ponderada de `0 a 100`:

| Métrica | Algoritmo / Cálculo | O que detecta para o vendedor |
| :--- | :--- | :--- |
| **Iluminação e Exposição** | Média do canal de luminância $\mu_Y \in [0, 255]$ | Fotos escuras de cozinha ($\mu_Y < 105$) ou estouradas por flash ($\mu_Y > 175$). |
| **Nitidez e Foco** | Variância do operador Laplaciano $\text{Var}(\nabla^2 I)$ | Lente suja de gordura, foto tremida ou fora de foco. |
| **Contraste Dinâmico** | Desvio padrão da luminância $\sigma_Y$ | Fotos opacas/"lavadas" ou com sombras excessivamente duras. |
| **Vivacidade de Cores** | Média do canal de Saturação ($S$) no espaço `HSV` | Alimentos com aparência pálida/fria sob luz fluorescente. |
| **Resolução de Catálogo** | Área em pixels ($W \times H$) e proporção | Fotos baixadas de WhatsApp ou miniaturas de baixa definição. |

### 3.2. Realce Gastronômico no Espaço de Cor CIE LAB
Diferente de filtros comuns que apenas aumentam brilho/contraste em `RGB` (o que distorce as cores da comida), o `FoodColorAndLightEnhancementStep` converte a imagem para o espaço perceptual **CIE LAB**:
1. **Canal $L$ (Luminosidade):** Aplica correção Gamma adaptativa (se a foto estiver subexposta) seguida de **CLAHE** (*Contrast Limited Adaptive Histogram Equalization*), revelando detalhes nas sombras do prato sem estourar os pontos claros.
2. **Canais $A$ (Verde–Vermelho) e $B$ (Azul–Amarelo):** Adiciona um deslocamento positivo controlado (*Warmth Shift*), neutralizando o aspecto azulado/frio de lâmpadas fluorescentes de cozinha e realçando tons quentes apetitosos (dourado de pães/frituras, vermelho de molhos/carnes, amarelo de queijos).
3. **Unsharp Mask:** Realça micro-texturas (gergelim, crosta, brilho de molho).

### 3.3. Sombra de Contato Elíptica Gaussiana
Para evitar que o prato recortado pareça "colado ou flutuando" sobre o novo fundo, o `StudioBackgroundGenerator` analisa os limites inferiores da máscara Alpha do alimento e projeta uma elipse sombreada com desfoque Gaussiano proporcional à largura da base do prato.

---

## 4. Escalabilidade, Performance e Observabilidade

1. **Non-Blocking Event Loop (`run_in_threadpool`):**
   Embora as rotas FastAPI sejam `async def` para leitura rápida de rede (`await file.read()`), o processamento matricial OpenCV/NumPy é *CPU-bound*. Todas as chamadas ao `quality_analyzer` e `pipeline_orchestrator` rodam via `run_in_threadpool`, mantendo o loop assíncrono livre para atender múltiplas requisições simultâneas.
2. **100% Stateless & In-Memory (`io.BytesIO`):**
   Nenhuma imagem enviada pelo usuário é gravada no disco do servidor. Todo o fluxo entra e sai via buffers de memória RAM, permitindo rodar múltiplos containers em **Docker / Kubernetes / Google Cloud Run / AWS ECS** com auto-scaling horizontal.
3. **Headers de Telemetria em Tempo Real:**
   Toda resposta do estúdio inclui cabeçalhos HTTP de observabilidade:
   - `X-Process-Time-Ms`: Tempo total HTTP.
   - `X-Studio-Total-Time-Ms`: Tempo total do endpoint de estúdio.
   - `X-Studio-Step-Timings-Ms`: Tempo individual de cada etapa do pipeline (ex: `background_removal:142.3,food_color_light_enhancement:38.1,studio_framing_and_composition:24.5`).
   - `X-Studio-Segmentation-Engine`: Motor utilizado (`rembg-onnx` ou `opencv-grabcut-fallback`).
   - `X-Studio-Final-Dimensions`: Resolução final entregue (ex: `1200x900`).
