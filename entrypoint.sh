#!/bin/bash
# =============================================================================
# ENTRYPOINT: Auto-run pipeline if processed assets are missing, then launch app
# =============================================================================
set -e

echo "=============================================="
echo "  Bus Analytics - Startup Check"
echo "=============================================="

# ---------------------------------------------------------------------------
# Define the critical asset files that the dashboard needs to function.
# If ANY of these are missing, we trigger the full pipeline.
# ---------------------------------------------------------------------------
ASSETS=(
    "data/1_bronze/data_raw.parquet"
    "data/1_bronze/bus_station.json"
    "data/2_silver/bus_gps_data.parquet"
    "data/2_silver/bus_station_data.json"
    "data/3_gold/ml_gold_data.parquet"
    "data/3_gold/dm_gold_data.parquet"
    "data/3_gold/inferred_route_data.json"
    "data/bunching.parquet"
    "data/domino_rules.parquet"
    "data/black_spot.parquet"
    "models/randomforest_model.pkl"
    "models/gradientboosting_model.pkl"
    "models/linear_regression_model.pkl"
)

MISSING=()
for asset in "${ASSETS[@]}"; do
    if [ ! -f "/app/$asset" ]; then
        MISSING+=("$asset")
    fi
done

# ---------------------------------------------------------------------------
# If assets are missing, run the pipeline stages in dependency order
# ---------------------------------------------------------------------------
if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    echo "[!] Missing ${#MISSING[@]} asset(s):"
    for m in "${MISSING[@]}"; do
        echo "    - $m"
    done
    echo ""
    echo ">>> Starting data pipeline to generate missing assets..."
    echo ""

    # --- Stage 0: Data Download from Kaggle ---
    if [ ! -d "/app/data/bus_gps" ] || [ -z "$(ls -A /app/data/bus_gps/sub_raw_* 2>/dev/null)" ]; then
        echo "[0/6] Missing raw GPS files. Downloading from Kaggle..."
        python -c "
import kagglehub
import os
import shutil
import glob
print('Downloading dataset...')
try:
    path = kagglehub.dataset_download('e42c91f126e0df5b66879f9bfcf72d437411e34cf8557bbdbfc446616781ef9c')
    target_dir = '/app/data/bus_gps'
    os.makedirs(target_dir, exist_ok=True)
    files = glob.glob(os.path.join(path, 'sub_raw_*'))
    if not files:
        print('Warning: No files starting with sub_raw_ found in dataset!')
    for f in files:
        dest = os.path.join(target_dir, os.path.basename(f))
        print(f'Moving {os.path.basename(f)} to {target_dir}')
        shutil.move(f, dest)
    print('Download and extraction complete.')
except Exception as e:
    print(f'Error downloading from Kaggle: {e}')
"
    else
        echo "[0/6] Raw GPS files already exist in data/bus_gps. Skipping download."
    fi

    # --- Stage 1: Bronze Layer ---
    if [ ! -f "/app/data/1_bronze/data_raw.parquet" ]; then
        echo "[1/6] Running Bronze Pipeline (raw GPS â†’ parquet)..."
        python -m pipelines.bronze_pipeline
        echo "      âœ“ Bronze data ready."
    else
        echo "[1/6] Bronze data_raw.parquet already exists. Skipping."
    fi

    # --- Stage 2: Bronze Bus Station (crawl) ---
    # NOTE: crawl_bus_station_pipeline requires a Chromium browser (DrissionPage).
    # In Docker, this is skipped. The bus_station.json MUST be pre-provided
    # via the volume mount (data/1_bronze/bus_station.json).
    if [ ! -f "/app/data/1_bronze/bus_station.json" ]; then
        echo "[2/6] WARNING: bus_station.json is missing!"
        echo "      The crawl pipeline requires a Chromium browser and cannot run in Docker."
        echo "      Please provide data/1_bronze/bus_station.json via volume mount."
        echo "      Attempting to run crawl anyway (may fail in headless container)..."
        python -m pipelines.crawl_bus_station_pipeline || echo "      âœ— Crawl failed (expected in Docker). Continuing..."
    else
        echo "[2/6] bus_station.json already exists. Skipping crawl."
    fi

    # --- Stage 3: Silver Layer ---
    if [ ! -f "/app/data/2_silver/bus_gps_data.parquet" ] || [ ! -f "/app/data/2_silver/bus_station_data.json" ]; then
        echo "[3/6] Running Silver Pipeline (cleaning + station mapping)..."
        python -m pipelines.silver_pipeline
        echo "      âœ“ Silver data ready."
    else
        echo "[3/6] Silver assets already exist. Skipping."
    fi

    # --- Stage 4: Gold Layer (Data Mining) ---
    if [ ! -f "/app/data/3_gold/dm_gold_data.parquet" ] || [ ! -f "/app/data/3_gold/inferred_route_data.json" ] || [ ! -f "/app/data/black_spot.parquet" ]; then
        echo "[4/6] Running DM Gold Pipeline (FP-Growth, route inference, black spots)..."
        python -m pipelines.dm_gold_pipeline
        echo "      âœ“ DM Gold data ready."
    else
        echo "[4/6] DM Gold assets already exist. Skipping."
    fi

    # --- Stage 5: Gold Layer (ML) + Model Training ---
    if [ ! -f "/app/data/3_gold/ml_gold_data.parquet" ]; then
        echo "[5/6] Running ML Gold Pipeline (feature engineering)..."
        python -m pipelines.ml_gold_pipeline
        echo "      âœ“ ML Gold data ready."
    else
        echo "[5/6] ML Gold data already exists. Skipping."
    fi

    if [ ! -f "/app/models/randomforest_model.pkl" ] || [ ! -f "/app/models/gradientboosting_model.pkl" ] || [ ! -f "/app/models/linear_regression_model.pkl" ]; then
        echo "[5b/6] Training ML models..."
        python -m models.train_ml_model
        echo "       âœ“ ML models trained."
    else
        echo "[5b/6] ML models already exist. Skipping."
    fi

    # --- Stage 6: Bunching Layer ---
    if [ ! -f "/app/data/bunching.parquet" ] || [ ! -f "/app/data/domino_rules.parquet" ]; then
        echo "[6/6] Running Bunching Pipeline..."
        python -m pipelines.bunching_pipeline
        echo "      âœ“ Bunching data ready."
    else
        echo "[6/6] Bunching assets already exist. Skipping."
    fi

    echo ""
    echo "=============================================="
    echo "  Pipeline complete! All assets generated."
    echo "=============================================="
else
    echo ""
    echo "[âœ“] All ${#ASSETS[@]} assets found. No pipeline execution needed."
fi

echo ""
echo ">>> Launching Streamlit dashboard..."
echo "=============================================="

exec streamlit run app/Dashboard.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true
