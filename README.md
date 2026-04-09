<p align="center">
  <h1 align="center">🚌 HCMC Bus Status Analysis & Prediction</h1>
  <p align="center">
    A Data Lakehouse prototype for analyzing Ho Chi Minh City's public bus GPS data using the <strong>Medallion Architecture</strong> (Bronze → Silver → Gold), with <strong>Machine Learning</strong> for travel‑time prediction and <strong>Data Mining</strong> for route inference.
  </p>
</p>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Dataset](#dataset)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Pipeline Execution Guide](#pipeline-execution-guide)
- [Machine Learning Models](#machine-learning-models)
- [Data Mining](#data-mining)
- [Streamlit Dashboard](#streamlit-dashboard)
- [Docker Deployment](#docker-deployment)
- [Current Status & Roadmap](#current-status--roadmap)

---

## Overview

This project processes **HCMC Bus GPS waypoint data** through a simulated **Data Lakehouse** architecture to:

1. **Predict bus travel duration** between stations using regression models (Linear Regression, Random Forest, Gradient Boosting).
2. **Infer bus routes** from raw GPS traces using FP-Growth frequent pattern mining.
3. **Visualize insights** through an interactive Streamlit dashboard for management-level (C-level) decision making.

> **⚠️ Prototype Status:** This is a working prototype that currently processes **static/batch data** stored as Parquet files. The long-term goal is to evolve into a real-time Data Lakehouse with Delta Lake as the storage layer.

---

## Architecture

The project follows the **Medallion Architecture** pattern:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA LAKEHOUSE (Simulated)                         │
│                                                                             │
│  ┌──────────────┐    ┌──────────────────┐    ┌────────────────────────┐     │
│  │   🥉 BRONZE   │───▶│    🥈 SILVER      │───▶│      🥇 GOLD          │     │
│  │  Raw GPS Data │    │ Cleaned + Station │    │ ML Features / DM Data │     │
│  │  (.parquet)   │    │ Mapping (.parquet)│    │     (.parquet)        │     │
│  └──────────────┘    └──────────────────┘    └──────────┬─────────────┘     │
│                                                         │                   │
│         Web Crawler ──▶ Bus Station Data (.json)        │                   │
└─────────────────────────────────────────────────────────┼───────────────────┘
                                                          │
                            ┌─────────────────────────────┼──────────┐
                            │                             ▼          │
                            │  ┌─────────────────┐  ┌──────────┐    │
                            │  │ 🤖 ML Models     │  │ ⛏️ Data  │    │
                            │  │ (Train & Predict)│  │  Mining  │    │
                            │  └────────┬────────┘  └─────┬────┘    │
                            │           │                 │         │
                            │           ▼                 ▼         │
                            │    ┌─────────────────────────────┐    │
                            │    │  📊 Streamlit Dashboard     │    │
                            │    │  (C-Level / Management UI)  │    │
                            │    └─────────────────────────────┘    │
                            └───────────────────────────────────────┘
```

### Data Flow

| Layer | Description | Storage |
|-------|------------|---------|
| **Bronze** | Raw GPS waypoints ingested from JSON files. Stratified sampling with 8 time-bins. | `data/1_bronze/data_raw.parquet` |
| **Silver** | Cleaned data (drop duplicates, remove unused columns, sort by vehicle/time). Enriched with nearest bus station via **BallTree** spatial query. | `data/2_silver/bus_gps_data.parquet` |
| **Gold (ML)** | Trajectory compression → station-pair extraction → Haversine distance, speed, duration, temporal features (hour, weekday). | `data/3_gold/ml_gold_data.parquet` |
| **Gold (DM)** | Trip segmentation with time-gap detection → FP-Growth frequent pattern mining → vehicle-to-route assignment. | `data/3_gold/dm_gold_data.parquet` |

---

## Dataset

**Source:** `HCMC_BUS_GPS_DATASET_ver_1.pdf` (Ho Chi Minh City Bus GPS Dataset)

The dataset consists of GPS waypoint messages from HCMC public buses containing:
- `vehicle` — bus identifier
- `x`, `y` — longitude/latitude coordinates
- `datetime` — UNIX timestamp
- `speed` — instantaneous speed
- `door_up`, `door_down`, `sos`, `driver`, `heading`, `aircon`, `working`, `ignition` — additional status fields

Supplementary data (bus station locations and routes) is crawled from the EBMS API (`apicms.ebms.vn`).

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Compute Engine** | Pandas + NumPy |
| **Storage Format** | Apache Parquet (PyArrow) — *Delta Lake planned* |
| **Spatial Query** | scikit-learn BallTree (Haversine) |
| **Machine Learning** | scikit-learn (Linear Regression, Random Forest, Gradient Boosting) |
| **Data Mining** | mlxtend (FP-Growth / Apriori), PrefixSpan, HDBSCAN |
| **Web Crawling** | DrissionPage (Cloudflare bypass) |
| **Dashboard** | Streamlit + Plotly + Folium |
| **Orchestration** | Dagster (Software-Defined Assets) |
| **Containerization** | Docker + Docker Compose (auto-pipeline entrypoint) |
| **Language** | Python 3.10+ |

---

## Project Structure

```
Bus-Status-Analysis-Prediction/
│
├── data/                               # 🗄️ Data Lake (simulated)
│   ├── bus_gps/                        # Raw GPS JSON chunks (sub_raw_*.json)
│   ├── 1_bronze/                       # Raw ingested data
│   │   ├── data_raw.parquet            #   GPS waypoints merged from JSON chunks
│   │   └── bus_station.json            #   Crawled bus station data
│   ├── 2_silver/                       # Cleaned & enriched data
│   │   ├── bus_gps_data.parquet        #   GPS with nearest station mapped (BallTree)
│   │   └── bus_station_data.json       #   Cleaned station metadata
│   ├── 3_gold/                         # Purpose-built analytical datasets
│   │   ├── ml_gold_data.parquet        #   Features for ML (station pairs, distance, duration)
│   │   ├── dm_gold_data.parquet        #   Features for DM (trips + inferred routes)
│   │   └── inferred_route_data.json    #   Route inference map
│   ├── bunching.parquet                # Bunching/Gapping analysis results
│   ├── domino_rules.parquet            # Domino cascade rules
│   └── black_spot.parquet              # Traffic black spot clusters
│
├── pipelines/                          # ⚙️ ETL Pipeline Scripts
│   ├── bronze_pipeline.py              # JSON chunks → Bronze Parquet
│   ├── crawl_bus_station_pipeline.py   # Web crawler for bus stations (EBMS API)
│   ├── silver_pipeline.py              # Bronze → Silver (cleaning + BallTree mapping)
│   ├── ml_gold_pipeline.py             # Silver → Gold ML (feature engineering)
│   ├── dm_gold_pipeline.py             # Silver → Gold DM (FP-Growth + route inference + black spots)
│   └── bunching_pipeline.py            # Gold DM → Bunching/Gapping analysis
│
├── orchestration/                      # 🔀 Dagster Orchestration
│   └── assets.py                       # Software-Defined Assets DAG
│
├── models/                             # 🧠 Trained ML Models
│   ├── train_ml_model.py               # Training script (3 algorithms)
│   ├── randomforest_model.pkl          # Trained Random Forest
│   ├── gradientboosting_model.pkl      # Trained Gradient Boosting
│   └── linear_regression_model.pkl     # Trained Linear Regression
│
├── app/                                # 📊 Streamlit Dashboard
│   ├── Dashboard.py                    # Entry point — KPI overview + Driver profiling
│   ├── helpers.py                      # Shared helper functions
│   └── pages/
│       ├── 1_Predict_Duration.py       # ML travel-time prediction
│       ├── 2_Black_Spot.py             # Traffic black spot map (HDBSCAN)
│       └── 3_Transit_Performance.py    # Bunching/Gapping performance analysis
│
├── config/
│   └── business_rules.yaml             # Business rule thresholds (KPIs, speed, violations)
│
├── utils/                              # 🔧 Shared utilities
│   └── config_loader.py                # YAML config loader
│
├── tests/                              # ✅ Unit Tests
│
├── notebook/                           # 📓 Jupyter Notebooks (Exploration)
│
├── Dockerfile                          # Python 3.10-slim + auto-pipeline entrypoint
├── docker-compose.yml                  # Single-service orchestration
├── entrypoint.sh                       # Auto-pipeline: check assets → run if missing → launch app
├── .dockerignore                       # Exclude unnecessary files from Docker build
├── requirements.txt                    # Python dependencies
├── vehicle_route_mapping.csv           # Vehicle ↔ Route reference mapping
└── project_structure.md                # Project structure (Vietnamese)
```

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **pip** or **Docker**

### Local Installation

```bash
# Clone the repository
git clone https://github.com/ZanissNguyen/Bus-Status-Analysis-Prediction.git
cd Bus-Status-Analysis-Prediction

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Data Setup

1. **Download the Dataset:** Download the HCMC Bus GPS dataset from [Kaggle](https://www.kaggle.com/datasets/e42c91f126e0df5b66879f9bfcf72d437411e34cf8557bbdbfc446616781ef9c).
2. **Extract & Move:** Extract all files with the prefix `sub_raw_` (e.g., `sub_raw_104.json`, `sub_raw_105.json`, etc.) and move them into the `data/bus_gps/` directory.

---

---

## Pipeline Execution Guide

Run the pipelines **in order** — each layer depends on the previous one:

```bash
# Step 1: Ingest raw GPS JSON files → Bronze layer (Parquet)
python -m pipelines.bronze_pipeline

# Step 1b (Optional): Crawl bus station data from EBMS API
python -m pipelines.crawl_bus_station_pipeline

# Step 2: Clean & enrich Bronze → Silver layer
python -m pipelines.silver_pipeline

# Step 3a: Feature engineering for ML (Silver → Gold)
python -m pipelines.ml_gold_pipeline

# Step 3b: Trip segmentation + Route inference + Black Spots (Silver → Gold)
python -m pipelines.dm_gold_pipeline

# Step 4: Train ML models on Gold data
python -m models.train_ml_model

# Step 5: Bunching/Gapping analysis
python -m pipelines.bunching_pipeline
```

> **💡 Tip:** When using Docker, the pipeline runs **automatically** if any output assets are missing. See [Docker Deployment](#docker-deployment) for details.

### Pipeline Details

| Step | Script | Input | Output | Key Operations |
|------|--------|-------|--------|----------------|
| 1 | `bronze_pipeline.py` | `data/bus_gps/*.json` | `data/1_bronze/data_raw.parquet` | JSON parsing, stratified sampling (8 time-bins) |
| 1b | `crawl_bus_station_pipeline.py` | EBMS API | `data/1_bronze/bus_station.json` | Cloudflare bypass, station metadata extraction |
| 2 | `silver_pipeline.py` | Bronze parquet + station JSON | `data/2_silver/` | Drop dupes, remove unused cols, BallTree nearest-station mapping |
| 3a | `ml_gold_pipeline.py` | Silver parquet | `data/3_gold/ml_gold_data.parquet` | Trajectory compression, station-pair generation, Haversine distance, speed calculation |
| 3b | `dm_gold_pipeline.py` | Silver parquet + station JSON | `data/3_gold/dm_gold_data.parquet` | Time-gap trip segmentation, FP-Growth mining, vehicle-route assignment, black spot detection |
| 4 | `train_ml_model.py` | Gold ML parquet | `models/*.pkl` | Feature engineering (cyclic hour, weekend flag, route avg), train 3 models |
| 5 | `bunching_pipeline.py` | Gold DM parquet | `data/bunching.parquet`, `data/domino_rules.parquet` | Headway analysis, bunching/gapping detection, domino cascade rules |

---

## Machine Learning Models

**Task:** Predict bus **travel duration (seconds)** between two consecutive stations.

### Features

| Feature | Type | Description |
|---------|------|-------------|
| `start station` | Categorical | Departure station name |
| `end station` | Categorical | Arrival station name |
| `distance (m)` | Numeric | Haversine distance between stations |
| `hour_sin`, `hour_cos` | Numeric | Cyclical encoding of departure hour |
| `weekend` | Binary | Weekend flag (Sat/Sun = 1) |
| `route_avg_duration` | Numeric | Historical average duration for this station pair |

### Models Trained

| Model | Encoding | Scaling | Key Hyperparameters |
|-------|----------|---------|---------------------|
| **Linear Regression** | OneHotEncoder | StandardScaler | — |
| **Random Forest** | OrdinalEncoder | Passthrough | `n_estimators=50, max_depth=12, min_samples_leaf=5` |
| **Gradient Boosting** | OneHotEncoder | Passthrough | `n_estimators=300, learning_rate=0.05, max_depth=3` |

### Evaluation Metrics

Models are evaluated with: **MAE**, **RMSE**, and **R² Score** on a 80/20 train-test split.

---

## Data Mining

**Task:** Infer which **bus route** each vehicle operates on, using only GPS traces (no ground-truth route labels).

### Approach

1. **Trip Segmentation** — GPS points grouped into trips using a configurable time-gap threshold (default: 70 min). A new trip starts when the gap between consecutive points exceeds the threshold.

2. **Station Filtering** — Only GPS points within **20m** of a known bus station are retained. Consecutive duplicates at the same station are compressed.

3. **FP-Growth Mining** — For each vehicle, the set of station visits across all trips is encoded as transactions. FP-Growth extracts the most frequent itemset (core stations).

4. **Route Matching** — Core stations are cross-referenced with a station↔route lookup table. The route with the highest frequency count is assigned to the vehicle.

### Threshold Tuning

The `pipelines/utils.py` module provides a **grid search** over trip-segmentation thresholds (15, 30, 45, 60, 90 min) to find the optimal balance between assigned vehicle count and core station quality.

---

## Streamlit Dashboard

The interactive dashboard provides C-level operational insights across **4 views**:

### 📊 Operational Dashboard (`Dashboard.py`)
- **5 KPI Cards:** Service health %, Bunching+Gapping %, Trip count, Avg headway, Safe driver %
- **Operational Risk Trends:** Stacked bar chart of bottleneck/bunching/gapping by hour
- **Network Performance:** Speed trends and station dwell time analysis
- **Deep-Dive Tabs:** Route rankings, station-pair speed heatmap, station error table, driver profiling
- **Global Filters:** Multi-route and date range filtering

### 🤖 Predict Duration (`1_Predict_Duration.py`)
- Input form for departure details and distance
- Predicts travel duration using trained ML models (RF, GB, LR)
- Fallback formula when no `.pkl` model is available

### 🔴 Black Spot Map (`2_Black_Spot.py`)
- Interactive Folium map of traffic black spots
- HDBSCAN clustering to identify dangerous zones
- Drill-down by route and area

### 🚌 Transit Performance (`3_Transit_Performance.py`)
- Bunching/Gapping analysis per route and station
- Service reliability metrics and trends
- Domino cascade rule visualization

### Running the Dashboard

```bash
streamlit run app/Dashboard.py
```

The dashboard will be available at `http://localhost:8501`.

---

## Docker Deployment

The Docker setup features **automatic pipeline execution** — when you run the container, it checks if all processed data assets exist. If any are missing, the pipeline runs automatically before launching the dashboard.

```bash
# Build and start (first run: pipeline auto-executes, subsequent runs: instant)
docker-compose up --build

# Access the dashboard
# http://localhost:8501
```

### How It Works

The `entrypoint.sh` script checks **13 critical asset files** across the data pipeline:

| Category | Assets Checked |
|----------|----------------|
| Bronze | `data_raw.parquet`, `bus_station.json` |
| Silver | `bus_gps_data.parquet`, `bus_station_data.json` |
| Gold | `ml_gold_data.parquet`, `dm_gold_data.parquet`, `inferred_route_data.json` |
| Analysis | `bunching.parquet`, `domino_rules.parquet`, `black_spot.parquet` |
| Models | `randomforest_model.pkl`, `gradientboosting_model.pkl`, `linear_regression_model.pkl` |

- **If ALL assets exist** → Pipeline is skipped, Streamlit launches immediately
- **If ANY asset is missing** → Only the required pipeline stages run (each stage is independently skippable)
- **Data persists** on host disk via volume mount (`.:/app`), so assets survive container restarts

> **⚠️ Note:** The crawl pipeline (`crawl_bus_station_pipeline.py`) requires a Chromium browser via DrissionPage, which cannot run inside the Docker container. Make sure `data/1_bronze/bus_station.json` is present before building.

---

## Current Status & Roadmap

### ✅ Completed

- [x] Bronze → Silver → Gold ETL pipeline (Medallion Architecture)
- [x] Bus station data web crawler (EBMS API + Cloudflare bypass)
- [x] BallTree spatial indexing for GPS-to-station mapping
- [x] ML feature engineering (trajectory compression, station pairs, temporal features)
- [x] Travel duration prediction with 3 regression models
- [x] FP-Growth route inference from GPS traces
- [x] Trip segmentation with configurable time-gap threshold
- [x] Bunching/Gapping analysis with domino cascade rules
- [x] Traffic black spot detection (HDBSCAN clustering)
- [x] Dagster orchestration (Software-Defined Assets DAG)
- [x] Streamlit Operational Dashboard (4 pages: KPI, Prediction, Black Spot, Transit Performance)
- [x] Driver profiling with hard-rule classification (Safe/Violator/Speedster/Reckless)
- [x] Configurable business rules via `config/business_rules.yaml`
- [x] Docker auto-pipeline deployment (entrypoint checks assets → runs pipeline if missing)
- [x] Unit tests for Gold layer refactoring

### 🗺️ Future Roadmap

- [ ] **Delta Lake integration** — Replace Parquet files with Delta tables for ACID transactions and time-travel
- [ ] **Real-time data ingestion** — Stream GPS data instead of batch processing static files
- [ ] **Real Data Lakehouse** — Upgrade architecture with proper storage layer (Delta Lake / Apache Iceberg)
- [ ] **Advanced ML models** — Explore deep learning (LSTM/Transformer) for sequence-based prediction
- [ ] **Route optimization** — Leverage data mining insights for route planning recommendations
- [ ] **API layer** — Add REST/GraphQL API for external consumption

---

## License

*To be determined.*

---

<p align="center">
  Built with ❤️ for HCMC public transit analytics
</p>
