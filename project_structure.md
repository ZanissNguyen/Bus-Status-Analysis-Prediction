hcmut_bus_analytics/
│
├── data/                       # 🗄️ Tầng Lưu trữ (Data Lake mô phỏng)
│   ├── 1_bronze/               # Chứa file raw ban đầu (vd: HCMC_BUS_GPS.json)
│   ├── 2_silver/               # Chứa file đã clean chung (bỏ missing, chuẩn hóa)
│   └── 3_gold/                 # Chứa dữ liệu đã biến đổi cho từng mục đích
│       ├── ml_features.csv     # Dành cho Linear Regression (đã scale, encode)
│       └── dm_transactions.csv # Dành cho Apriori/FP-Growth (dạng giỏ hàng/rời rạc)
│
├── pipelines/                  # ⚙️ Tầng Xử lý Dữ liệu (ETL Scripts)
│   ├── 01_raw_to_silver.py     # Script làm sạch chung (Người làm Data Prep chịu trách nhiệm)
│   ├── 02a_silver_to_gold_ml.py # Script trích xuất đặc trưng ML (Người làm ML phụ trách)
│   └── 02b_silver_to_gold_dm.py # Script rời rạc hóa dữ liệu DM (Người làm DM phụ trách)
│
├── models/                     # 🧠 Nơi lưu model đã huấn luyện
│   ├── train_ml_model.py       # Script train Linear Regression và lưu file
│   └── duration_predictor.pkl  # File model (được tạo ra sau khi chạy script trên)
│
├── app/                        # 📊 Tầng Giao diện (Streamlit Dashboard)
│   ├── main.py                 # File entry-point của Dashboard
│   ├── pages/                  # Dùng nếu muốn chia nhiều tab (vd: ML Tab, DM Tab)
│   │   ├── 1_predict_duration.py 
│   │   └── 2_route_insights.py
│   └── utils.py                # Chứa các hàm vẽ biểu đồ tĩnh, load model
│
├── Dockerfile                  # Cấu hình môi trường Python & cài đặt thư viện
├── docker-compose.yml          # Cấu hình chạy toàn bộ hệ thống
├── requirements.txt            # Danh sách thư viện (pandas, scikit-learn, streamlit...)
└── README.md                   # Hướng dẫn chi tiết cách chạy cho C-level/Thầy cô