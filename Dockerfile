# ============================================================
#  CAAS — FastAPI Inference Server
#  Multi-stage build: keeps final image small (~300MB)
#
#  Build:
#    docker build -t caas-api .
#
#  Run locally:
#    docker run -p 8000:8000 \
#      -v $(pwd)/03_Data:/app/03_Data \
#      caas-api
#
#  Run on EC2 (models baked in):
#    docker run -d -p 8000:8000 caas-api
#
#  Test:
#    curl http://localhost:8000/health
# ============================================================

# ── Stage 1: Builder — install dependencies ─────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools needed by some packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-serve.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements-serve.txt


# ── Stage 2: Runtime — copy only what's needed ─────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# libgomp1 is required at runtime by LightGBM (OpenMP)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy the project structure the API depends on:
#   04_Scripts/serve/app.py   ← FastAPI application
#   03_Data/models/           ← LightGBM (champion) + XGBoost (fallback) + scalers
#   03_Data/processed/        ← features.csv, pm25_consolidated.csv
#   03_Data/results/          ← lightgbm_summary.json + xgboost_summary.json
COPY 04_Scripts/serve/app.py       04_Scripts/serve/app.py
COPY 04_Scripts/serve/dashboard.py 04_Scripts/serve/dashboard.py
COPY 03_Data/models/          03_Data/models/
COPY 03_Data/processed/features.csv         03_Data/processed/features.csv
COPY 03_Data/processed/pm25_consolidated.csv 03_Data/processed/pm25_consolidated.csv
COPY 03_Data/results/lightgbm_summary.json  03_Data/results/lightgbm_summary.json
COPY 03_Data/results/xgboost_summary.json   03_Data/results/xgboost_summary.json

# Non-root user for security
RUN useradd -m caas
USER caas

# Expose FastAPI port
EXPOSE 8000

# Health check — Docker will restart container if /health fails.
# start-period=60s: cold boot loads 6 model files (LightGBM x3 + XGBoost x3) before /health responds.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Start the API.
# --workers 1: single worker loads models once into memory (~200 MB).
# Running 2+ workers on t3.small (2 GB RAM, no swap) OOM-kills the box.
WORKDIR /app/04_Scripts/serve
CMD ["uvicorn", "app:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1"]
