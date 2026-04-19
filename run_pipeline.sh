#!/bin/bash
# ============================================================
#  CAAS — Master Pipeline Runner
#  Run this script on your local machine step by step.
#  Each step is numbered and can be run independently.
# ============================================================

set -e  # Stop on any error

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS="$BASE_DIR/04_Scripts"
ENV_NAME="caas-env"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

log()  { echo -e "${BLUE}[CAAS]${NC} $1"; }
ok()   { echo -e "${GREEN}[✅ DONE]${NC} $1"; }
warn() { echo -e "${YELLOW}[⚠️  WARN]${NC} $1"; }
err()  { echo -e "${RED}[❌ ERROR]${NC} $1"; exit 1; }

STEP=${1:-"all"}   # Pass step name or "all"

# ── Step 0: Setup virtual environment ──────────────────────
setup_env() {
    log "Setting up Python virtual environment..."
    if [ ! -d "$BASE_DIR/$ENV_NAME" ]; then
        python3 -m venv "$BASE_DIR/$ENV_NAME"
        ok "Virtual environment created: $ENV_NAME"
    else
        warn "venv already exists — skipping creation"
    fi
    source "$BASE_DIR/$ENV_NAME/bin/activate"
    pip install -r "$BASE_DIR/requirements.txt" -q
    ok "Dependencies installed"
}

# ── Step 1: Parse PM2.5 data ────────────────────────────────
step1_pm25() {
    log "Step 1: Parsing PM2.5 Excel files..."
    python "$SCRIPTS/parse_pm25.py"
    ok "PM2.5 data parsed → 03_Data/processed/pm25_consolidated.csv"
}

# ── Step 2: Fetch weather data ──────────────────────────────
step2_weather() {
    log "Step 2: Fetching weather data from Open-Meteo..."
    python "$SCRIPTS/fetch_weather.py"
    ok "Weather data fetched → 03_Data/processed/weather_chiang_mai.csv"
}

# ── Step 3: Fetch FIRMS fire data ───────────────────────────
step3_firms() {
    log "Step 3: Fetching NASA FIRMS fire hotspot data..."
    if [ -z "$FIRMS_MAP_KEY" ]; then
        source "$BASE_DIR/.env" 2>/dev/null || true
    fi
    if [ -z "$FIRMS_MAP_KEY" ]; then
        err "FIRMS_MAP_KEY not set. Add it to .env file."
    fi
    python "$SCRIPTS/fetch_firms.py"
    ok "FIRMS data fetched → 03_Data/processed/firms_consolidated.csv"
}

# ── Step 4: Build features ──────────────────────────────────
step4_features() {
    log "Step 4: Building feature matrix (45 features)..."
    python "$SCRIPTS/build_features.py"
    ok "Features built → 03_Data/processed/features.csv"
}

# ── Step 5: Train XGBoost ───────────────────────────────────
step5_xgboost() {
    log "Step 5: Training XGBoost models (t+1, t+3, t+7)..."
    log "  This takes ~5-10 minutes. MLflow runs will be logged."
    python "$SCRIPTS/train_xgboost.py"
    ok "XGBoost trained → 03_Data/models/xgboost_t*.json"
    ok "Results → 03_Data/results/xgboost_summary.json"
}

# ── Step 6: Train LSTM ──────────────────────────────────────
step6_lstm() {
    log "Step 6: Training LSTM models (t+1, t+3, t+7)..."
    log "  This takes ~1-2 hours on CPU. Run overnight."
    python "$SCRIPTS/train_lstm.py"
    ok "LSTM trained → 03_Data/models/lstm_t*.keras"
    ok "Results → 03_Data/results/lstm_summary.json"
}

# ── Step 7: Start FastAPI ───────────────────────────────────
step7_api() {
    log "Step 7: Starting FastAPI server on http://localhost:8000"
    log "  Press Ctrl+C to stop"
    cd "$SCRIPTS/serve"
    uvicorn app:app --reload --port 8000
}

# ── Step 8: Start Streamlit ─────────────────────────────────
step8_dashboard() {
    log "Step 8: Starting Streamlit dashboard on http://localhost:8501"
    log "  Make sure FastAPI is running first (step 7 in another terminal)"
    log "  Press Ctrl+C to stop"
    streamlit run "$SCRIPTS/serve/dashboard.py" --server.port 8501
}

# ── Step 9: Run drift monitoring ────────────────────────────
step9_monitoring() {
    log "Step 9: Running Evidently drift monitoring..."
    python "$SCRIPTS/monitoring/evidently_report.py"
    ok "Drift report → 03_Data/results/drift_report_*.html"
}

# ── Step 10: MLflow UI ──────────────────────────────────────
step10_mlflow() {
    log "Step 10: Starting MLflow UI on http://localhost:5000"
    mlflow ui --backend-store-uri "$BASE_DIR/mlruns" --port 5000
}

# ── Main ────────────────────────────────────────────────────
echo ""
echo "========================================"
echo "  CAAS Pipeline Runner"
echo "========================================"
echo ""

case "$STEP" in
    "setup")   setup_env ;;
    "1"|"pm25")      source "$BASE_DIR/$ENV_NAME/bin/activate" && step1_pm25 ;;
    "2"|"weather")   source "$BASE_DIR/$ENV_NAME/bin/activate" && step2_weather ;;
    "3"|"firms")     source "$BASE_DIR/$ENV_NAME/bin/activate" && step3_firms ;;
    "4"|"features")  source "$BASE_DIR/$ENV_NAME/bin/activate" && step4_features ;;
    "5"|"xgboost")   source "$BASE_DIR/$ENV_NAME/bin/activate" && step5_xgboost ;;
    "6"|"lstm")      source "$BASE_DIR/$ENV_NAME/bin/activate" && step6_lstm ;;
    "7"|"api")       source "$BASE_DIR/$ENV_NAME/bin/activate" && step7_api ;;
    "8"|"dashboard") source "$BASE_DIR/$ENV_NAME/bin/activate" && step8_dashboard ;;
    "9"|"monitor")   source "$BASE_DIR/$ENV_NAME/bin/activate" && step9_monitoring ;;
    "10"|"mlflow")   source "$BASE_DIR/$ENV_NAME/bin/activate" && step10_mlflow ;;
    "data")
        # Run all data steps (1+2+3+4) — no training
        setup_env
        step1_pm25
        step2_weather
        step3_firms
        step4_features
        log "All data steps complete. Run './run_pipeline.sh 5' to train XGBoost."
        ;;
    "train")
        # Run training steps only (5+6)
        source "$BASE_DIR/$ENV_NAME/bin/activate"
        step5_xgboost
        log "XGBoost done. Run './run_pipeline.sh 6' to train LSTM (optional, ~1-2h)."
        ;;
    "serve")
        # Start API + dashboard (needs training done first)
        source "$BASE_DIR/$ENV_NAME/bin/activate"
        log "Starting FastAPI in background..."
        cd "$SCRIPTS/serve" && uvicorn app:app --port 8000 &
        sleep 3
        step8_dashboard
        ;;
    "all"|*)
        log "Running full pipeline (Steps 0-5)..."
        log "NOTE: LSTM (step 6) is skipped in 'all' mode — run separately overnight."
        echo ""
        setup_env
        step1_pm25
        step2_weather
        step3_firms
        step4_features
        step5_xgboost
        echo ""
        ok "========================================"
        ok "  Full pipeline complete!"
        ok "========================================"
        echo ""
        log "Next steps:"
        log "  ./run_pipeline.sh 6        — Train LSTM (optional, ~2h)"
        log "  ./run_pipeline.sh 7        — Start FastAPI server"
        log "  ./run_pipeline.sh 8        — Start Streamlit dashboard"
        log "  ./run_pipeline.sh 10       — Open MLflow UI"
        ;;
esac
