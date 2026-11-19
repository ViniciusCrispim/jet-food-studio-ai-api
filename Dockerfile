# ==============================================================================
# STAGE 1: Builder (Compilação isolada das dependências Python)
# ==============================================================================
FROM python:3.10-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Instala as dependências em um ambiente virtual isolado para cópia limpa no Stage 2
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt


# ==============================================================================
# STAGE 2: Production Runtime (Container leve, seguro e desacoplado dos pesos IA)
# ==============================================================================
FROM python:3.10-slim AS runtime

# Variáveis de ambiente para otimização de inferência CPU (OpenCV / ONNX Runtime)
# Evita CPU thrashing quando múltiplos workers atendem requisições simultâneas
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    U2NET_HOME="/home/appuser/.u2net" \
    AI_MODEL_NAME="isnet-general-use" \
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    MKL_NUM_THREADS=2 \
    ORT_NUM_THREADS=2 \
    APP_ENV="production" \
    DEBUG="false" \
    HOST="0.0.0.0" \
    PORT="8000" \
    WORKERS="2"

# Bibliotecas nativas mínimas necessárias para OpenCV Headless e ONNX Runtime + curl para Healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cria usuário não-root por segurança e diretório para montagem do Volume de modelos IA
RUN groupadd -r appgroup && \
    useradd -r -g appgroup -m -d /home/appuser appuser && \
    mkdir -p /home/appuser/.u2net && \
    chown -R appuser:appgroup /home/appuser/.u2net

WORKDIR /app

# Copia apenas o ambiente virtual enxuto do Stage 1 (sem chumbamento de modelos pesados na imagem)
COPY --from=builder /opt/venv /opt/venv

# Copia o código-fonte da aplicação
COPY --chown=appuser:appgroup app ./app
COPY --chown=appuser:appgroup .env.example ./.env

# Declara o ponto de montagem do volume persistente para cache de modelos ONNX (.u2net)
VOLUME ["/home/appuser/.u2net"]

USER appuser

EXPOSE 8000

# Healthcheck nativo do Docker verificando se a API e o motor de IA estão operacionais
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Executa Uvicorn com múltiplos workers configuráveis para alta concorrência
CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST} --port ${PORT} --workers ${WORKERS} --no-access-log"]
