# Pipeline Machine Learning Gold (`ml_gold_pipeline.py`)

> Pipeline tạo dataset Gold phục vụ huấn luyện mô hình ML dự đoán thời gian di chuyển giữa các trạm xe buýt. Đi kèm với `models/train_ml_model.py` để train 3 mô hình hồi quy.

---

## Tổng quan

**Input:** `data/2_silver/bus_gps_data.parquet`
**Output:** `data/3_gold/ml_gold_data.parquet`

```
Silver GPS ──→ [1] Lọc tại trạm ──→ [2] Nén block ──→ [3] Tạo cặp (Start→End)
                                                              │
                    ┌─────────────────────────────────────────┘
                    ▼
              [4] Haversine ──→ [5] Datetime Features ──→ [6] Final Filter ──→ Lưu Parquet
                                                                                    │
                    ┌───────────────────────────────────────────────────────────────┘
                    ▼
              [train_ml_model.py] ──→ 3 file .pkl (LR, RF, GB)
```

---

## Các bước xử lý (`prepare_ml_data`)

### Bước 1 — Lọc điểm tại trạm

```python
df_ml = df_ml[df_ml['station_distance'] <= 50]  # station_distance_max_m
```

Chỉ giữ các bản ghi GPS nằm trong bán kính 50m quanh trạm. Các điểm giữa đường bị loại vì không cung cấp thông tin về thời gian dừng/khởi hành.

### Bước 2 — Nén block liên tiếp

Khi xe dừng tại 1 trạm, GPS phát nhiều bản ghi liên tiếp cùng trạm. Pipeline nén lại chỉ giữ **1 điểm có `station_distance` nhỏ nhất** (gần tâm trạm nhất):

```python
is_new_block = (df['current_station'] != df['current_station'].shift(1)) | \
               (df['vehicle'] != df['vehicle'].shift(1))
df['block_id'] = is_new_block.cumsum()
idx_min = df.groupby('block_id')['station_distance'].idxmin()
df_compressed = df.loc[idx_min]
```

> Kỹ thuật giống hệt `preprocess_data` trong pipeline 3.2, nhưng ở đây phục vụ ML thay vì Data Mining.

### Bước 3 — Tạo cặp trạm (Start → End)

Dùng `shift(-1)` kéo dòng tiếp theo lên để ghép cặp:

```python
df['end station']    = df.groupby('vehicle')['current_station'].shift(-1)
df['end_time_unix']  = df.groupby('vehicle')['datetime'].shift(-1)
df['end_x']          = df.groupby('vehicle')['x'].shift(-1)
df['end_y']          = df.groupby('vehicle')['y'].shift(-1)
```

Sau đó loại bỏ:
- Dòng cuối mỗi xe (không có trạm tiếp theo → NaN)
- Cặp trùng (`start station == end station` — xe dừng 2 lần cùng bến)

**Output:** Mỗi row = 1 chuyến **liên trạm** `(A → B)`

### Bước 4 — Tính khoảng cách Haversine (Vectorized Numpy)

```python
# Chuyển tọa độ sang radian
lat1, lng1 = np.radians(df['y']), np.radians(df['x'])
lat2, lng2 = np.radians(df['end_y']), np.radians(df['end_x'])

# Haversine formula
a = sin²(Δlat/2) + cos(lat1) × cos(lat2) × sin²(Δlng/2)
a = clip(a, 0, 1)  # Chống lỗi float âm
c = 2 × arcsin(√a)
distance_m = 6,371,000 × c
```

Tính toán chạy **toàn bộ DataFrame 1 lần** (không dùng vòng lặp) nhờ Numpy broadcasting.

### Bước 5 — Tính thời gian + trích xuất features

```python
df['duration (s)'] = df['end_time_unix'] - df['datetime']  # Hiệu 2 unix timestamp
```

Thời gian bằng 0 → thay bằng NaN (tránh chia cho 0 khi tính speed).

### Bước 6 — Final Filter

Loại bỏ dữ liệu bất thường trước khi đưa vào ML:

| Điều kiện | Ngưỡng | Mục đích |
|-----------|--------|----------|
| `is_same_day` | start.date == end.date | Loại chuyến qua đêm |
| `distance (m) > 100` | 100m | Loại cặp trạm quá gần (lỗi GPS) |
| `duration (s) > 10` | 10s | Loại chuyến di chuyển phi thực tế |

**Output schema (`ml_gold_data.parquet`) — 6 cột:**

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `start station` | string | Trạm xuất phát |
| `end station` | string | Trạm đích |
| `hour` | int | Giờ khởi hành (0-23) |
| `week day` | int | Ngày trong tuần (0=T2, 6=CN) |
| `distance (m)` | float | Khoảng cách Haversine (mét) |
| `duration (s)` | float | **Biến mục tiêu** — thời gian di chuyển (giây) |

---

## Huấn luyện mô hình (`models/train_ml_model.py`)

### Feature Engineering bổ sung

Trước khi train, script thêm 4 đặc trưng từ 6 cột Gold:

| Feature mới | Công thức | Mục đích |
|-------------|-----------|----------|
| `weekend` | `1` nếu `week day ≥ 5` | Binary flag cuối tuần |
| `hour_sin` | `sin(2π × hour / 24)` | Cyclic encoding (23h gần 0h) |
| `hour_cos` | `cos(2π × hour / 24)` | Cyclic encoding (bổ sung) |
| `route_avg_duration` | `mean(duration)` theo cặp trạm | Baseline lịch sử |

> Sau khi tạo xong, cột `hour` và `week day` gốc bị **drop** — model chỉ thấy phiên bản encoded.

### 3 mô hình được huấn luyện

| Mô hình | Preprocessor | Hyperparameters |
|---------|-------------|-----------------|
| **Linear Regression** | OneHotEncoder + StandardScaler | — (baseline) |
| **Random Forest** | OrdinalEncoder + passthrough | n_estimators=50, max_depth=12, min_samples_leaf=5 |
| **Gradient Boosting** | OneHotEncoder + passthrough | n_estimators=300, lr=0.05, max_depth=3 |

**Feature Vector cuối cùng (7 cột):**

| Cột | Loại | Preprocessor |
|-----|------|-------------|
| `start station` | Categorical | OneHot / Ordinal |
| `end station` | Categorical | OneHot / Ordinal |
| `distance (m)` | Numeric | Scale / Passthrough |
| `weekend` | Binary | Scale / Passthrough |
| `hour_sin` | Float | Scale / Passthrough |
| `hour_cos` | Float | Scale / Passthrough |
| `route_avg_duration` | Float | Scale / Passthrough |

**Train/Test split:** 80/20 (`random_state=42`)
**Biến mục tiêu:** `duration (s)`
**Metrics:** MAE, RMSE, R²

### Output

3 file pickle tại `models/`:

| File | Nội dung |
|------|----------|
| `linear_regression_model.pkl` | sklearn Pipeline (preprocessor + LR) |
| `randomforest_model.pkl` | sklearn Pipeline (preprocessor + RF) |
| `gradientboosting_model.pkl` | sklearn Pipeline (preprocessor + GB) |

> Mỗi `.pkl` chứa **toàn bộ Pipeline** (preprocessor + model), nên khi inference chỉ cần `model.predict(raw_df)` mà không cần transform thủ công.

---

## Inference trên Dashboard

File `app/pages/1_Predict_Duration.py` load 3 file `.pkl` và dữ liệu Gold để:

1. User chọn trạm đầu, trạm cuối, giờ, cuối tuần
2. Tự động tra `route_avg_duration` và `distance` từ lịch sử Gold
3. Tạo feature vector 7 cột giống hệt lúc train
4. Gọi `.predict()` trên cả 3 model → hiển thị kết quả so sánh

---

## Cách chạy

```bash
# Bước 1: Tạo dataset Gold-ML (cần Silver sẵn sàng)
python -m pipelines.ml_gold_pipeline

# Bước 2: Train 3 models (cần Gold-ML sẵn sàng)
python -m models.train_ml_model
```

**Tiền điều kiện:**
- `data/2_silver/bus_gps_data.parquet` ✅
- `config/business_rules.yaml` ✅ (dùng `station_distance_max_m`)

---

## Config liên quan (`business_rules.yaml`)

| Key | Giá trị | Dùng ở |
|-----|---------|--------|
| `station_distance_max_m` | 50 | Lọc điểm tại trạm (Bước 1) |
| `earth_radius_m` | 6371000 | Haversine (Bước 4) |

---

*Tham chiếu: [architecture.md](architecture.md) · [data_mining_gold.md](data_mining_gold.md)*
