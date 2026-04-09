# Project Structure

```
Bus-Status-Analysis-Prediction/
│
├── data/                               # 🗄️ Tầng Lưu trữ (Data Lake mô phỏng)
│   ├── bus_gps/                        # Dữ liệu GPS thô (sub_raw_*.json)
│   ├── 1_bronze/                       # Tầng Bronze — dữ liệu thô đã gộp
│   │   ├── data_raw.parquet            #   GPS waypoints gộp từ JSON chunks
│   │   └── bus_station.json            #   Dữ liệu trạm xe buýt (crawl từ EBMS API)
│   ├── 2_silver/                       # Tầng Silver — dữ liệu đã làm sạch
│   │   ├── bus_gps_data.parquet        #   GPS đã clean + mapping trạm gần nhất (BallTree)
│   │   └── bus_station_data.json       #   Metadata trạm đã chuẩn hóa
│   └── 3_gold/                         # Tầng Gold — dữ liệu phân tích chuyên biệt
│       ├── ml_gold_data.parquet        #   Features cho ML (cặp trạm, khoảng cách, thời lượng)
│       ├── dm_gold_data.parquet        #   Features cho Data Mining (trips + inferred routes)
│       └── inferred_route_data.json    #   Bản đồ suy luận tuyến xe
│
├── pipelines/                          # ⚙️ Tầng Xử lý Dữ liệu (ETL Scripts)
│   ├── bronze_pipeline.py              # JSON chunks → Bronze Parquet
│   ├── crawl_bus_station_pipeline.py   # Web crawler trạm xe buýt (EBMS API + DrissionPage)
│   ├── silver_pipeline.py              # Bronze → Silver (làm sạch + BallTree mapping)
│   ├── ml_gold_pipeline.py             # Silver → Gold ML (feature engineering cho ML)
│   ├── dm_gold_pipeline.py             # Silver → Gold DM (trip segmentation + FP-Growth + Black Spot)
│   └── bunching_pipeline.py            # Gold DM → Bunching/Gapping analysis
│
├── orchestration/                      # 🔀 Dagster Orchestration (Software-Defined Assets)
│   └── assets.py                       # Định nghĩa DAG pipeline: Bronze → Silver → Gold → ML → Bunching
│
├── models/                             # 🧠 Trained ML Models
│   ├── train_ml_model.py               # Script huấn luyện 3 thuật toán hồi quy
│   ├── randomforest_model.pkl          # Random Forest (đã train)
│   ├── gradientboosting_model.pkl      # Gradient Boosting (đã train)
│   └── linear_regression_model.pkl     # Linear Regression (đã train)
│
├── app/                                # 📊 Streamlit Dashboard (Operational Excellence)
│   ├── Dashboard.py                    # Entry point — KPI tổng quan + Driver Profiling
│   ├── helpers.py                      # Hàm tiện ích dùng chung (load data, format, ...)
│   └── pages/
│       ├── 1_Predict_Duration.py       # Dự đoán thời gian di chuyển (ML models)
│       ├── 2_Black_Spot.py             # Bản đồ điểm đen giao thông (HDBSCAN clustering)
│       └── 3_Transit_Performance.py    # Phân tích Bunching/Gapping theo tuyến & trạm
│
├── config/
│   └── business_rules.yaml             # Cấu hình ngưỡng nghiệp vụ (KPI, tốc độ, vi phạm, ...)
│
├── utils/                              # 🔧 Tiện ích dùng chung
│   └── config_loader.py                # Load YAML config
│
├── tests/                              # ✅ Unit Tests
│
├── notebook/                           # 📓 Jupyter Notebooks (Exploration & Benchmarking)
│
├── Dockerfile                          # Docker image (Python 3.10-slim + entrypoint)
├── docker-compose.yml                  # Docker Compose — single-service orchestration
├── entrypoint.sh                       # Auto-pipeline: kiểm tra assets → chạy pipeline nếu thiếu → launch Streamlit
├── .dockerignore                       # Loại trừ file không cần thiết khỏi Docker build context
├── requirements.txt                    # Danh sách thư viện Python
├── vehicle_route_mapping.csv           # Bảng tham chiếu Vehicle ↔ Route
├── project_structure.md                # Cấu trúc dự án (file này)
└── README.md                           # Hướng dẫn tổng quan dự án
```