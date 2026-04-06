# Pipeline Data Mining Gold (`3.2_data_mining_gold.py`)

> Pipeline xử lý dữ liệu Silver GPS thành Gold layer phục vụ phân tích vận hành. Bao gồm: nhận diện tuyến xe, phân chuyến, tính tốc độ, và trích xuất điểm kẹt xe (black spot).

---

## Tổng quan

**Input:** `data/2_silver/bus_gps_data.parquet` + `bus_station_data.json`
**Output:** 3 file

| File | Mô tả |
|------|-------|
| `data/3_gold/dm_gold_data.parquet` | GPS Silver + trip_id + inferred_route + avg_speed |
| `data/3_gold/infered_route_data.json` | Kết quả nhận diện tuyến từng xe |
| `data/black_spot.parquet` | Các điểm GPS đang kẹt xe |

**Luồng xử lý chính:**

```
Silver GPS ──→ [1] Nén trạm ──→ [2] Phân chuyến ──→ [3] Nhận diện tuyến (FP-Growth)
                                                            │
                           ┌────────────────────────────────┘
                           ▼
               [4] Merge route → GPS ──→ [5] Chia lại chuyến ──→ [6] Tính avg_speed
                                                                       │
                                                                       ▼
                                                         [7] Trích black spot ──→ Lưu
```

---

## Các bước xử lý

### Bước 1 — Nén dữ liệu trạm (`preprocess_data`)

**Mục tiêu:** Từ ~N triệu bản ghi GPS, giữ lại chỉ 1 điểm đại diện mỗi lần xe ghé 1 trạm.

**Logic:**
1. Lọc `station_distance ≤ 50m` (chỉ giữ điểm "tại trạm")
2. Gom các điểm GPS liên tiếp cùng xe + cùng trạm thành **block**
3. Mỗi block chỉ giữ điểm có `station_distance` nhỏ nhất (gần tâm trạm nhất)

**Kỹ thuật:** Dùng `shift(1)` phát hiện ranh giới block → `cumsum()` tạo block_id → `groupby().idxmin()` chọn đại diện.

> Kết quả: Dataset giảm đáng kể (ví dụ 12M → 500K dòng) mà vẫn giữ đủ thông tin thứ tự ghé trạm.

---

### Bước 2 — Phân chuyến (`split_trip_date`)

**Mục tiêu:** Tách dòng GPS liên tục thành các chuyến đi riêng biệt (trip).

**Logic:** Một chuyến mới bắt đầu khi:
- Là bản ghi đầu tiên của xe (`time_diff` = NaN)
- HOẶC khoảng cách thời gian > `trip_split_max_gap_sec` = **4200s (70 phút)**

**Output:** Cột `trip_id` — ID chuyến rolling cho mỗi xe.

> Ví dụ: Xe 51B-123 có trip_id = 1, 2, 3... Xe 51B-456 có trip_id = 1, 2... (reset theo xe).

---

### Bước 3 — Nhận diện tuyến (`infer_route_dynamic_tracking`)

**Mục tiêu:** Xác định xe đang chạy tuyến nào, **kể cả khi xe đổi tuyến giữa chừng**.

Đây là thuật toán phức tạp nhất của pipeline, gồm 2 tầng:

#### Tầng 1 — Dynamic Drift Tracking (phát hiện đổi tuyến)

Với mỗi xe, duyệt tuần tự qua các trip:

```
Trip 1 → Thêm vào Memory Pool (tập trạm đã thấy)
Trip 2 → Tính overlap_ratio = (trạm chung với Pool) / (tổng trạm trip 2)
         Nếu overlap < 0.5 → ĐỔI TUYẾN! Chốt sổ segment cũ, reset Pool
         Nếu overlap ≥ 0.5 → Cùng tuyến, cập nhật Pool
Trip 3 → Tương tự...
```

**Ngưỡng drift:** `route_drift_threshold = 0.5` — nếu < 50% trạm trùng → đổi tuyến.

#### Tầng 2 — FP-Growth + Majority Voting (nhận diện tuyến cụ thể)

Với mỗi segment (nhóm trip cùng tuyến):

1. Encode danh sách trạm các trip thành binary matrix (`TransactionEncoder`)
2. **Pre-check bùng nổ:** Nếu ≥ 20 trạm có support cao → bỏ qua FP-Growth, dùng luôn
3. **FP-Growth:** Tìm tập trạm xuất hiện thường xuyên nhất (support ≥ 0.6)
4. **Majority Voting:** Tra từ điển `trạm → [tuyến]`, đếm phiếu bầu, chọn tuyến có phiếu cao nhất
5. Nếu hòa phiếu → bỏ qua segment (không chắc chắn)

**Output:** `infered_route_data.json` — mỗi row là `{vehicle, start_trip_id, end_trip_id, inferred_route}`

**Ngưỡng loại bỏ:**

| Điều kiện | Ngưỡng | Ý nghĩa |
|-----------|--------|---------|
| `min_trips_per_segment` | 2 | Segment phải có ≥ 2 trip |
| `min_stations_per_trip` | 2 | Phải có ≥ 2 trạm unique |
| `core_stations_min_count` | 2 | FP-Growth phải tìm được ≥ 2 trạm core |
| `fpgrowth_explosion_threshold` | 20 | Bỏ qua FP-Growth nếu ≥ 20 trạm frequent |

---

### Bước 4 — Merge route vào GPS (`merge_asof`)

**Vấn đề:** `inferred_route` chỉ biết ở cấp segment (`start_trip_id → end_trip_id`), cần gán ngược cho từng bản ghi GPS.

**Giải pháp:** `pd.merge_asof` — nội suy backward:

```python
pd.merge_asof(
    silver_df,           # trip_id từng bản ghi GPS
    inferred_df,         # start_trip_id → inferred_route
    left_on='trip_id',
    right_on='start_trip_id',
    by='vehicle',
    direction='backward' # Tìm start_trip_id ≤ trip_id gần nhất
)
```

Sau đó lọc: chỉ giữ `trip_id ≤ end_trip_id` (loại bỏ trip nằm ngoài range).

> **Tại sao dùng `merge_asof` thay vì `merge`?** Vì trip_id và start_trip_id không khớp 1:1. `merge_asof` tìm giá trị gần nhất thay vì exact match, tránh Cartesian product bùng RAM.

---

### Bước 5 — Chia lại chuyến theo Route (`re_split_trips_by_route`)

**Mục tiêu:** Sau khi gán tuyến, chia lại `trip_id` chính xác hơn dựa trên thứ tự trạm thực tế.

**Logic cắt chuyến mới khi:**

| Điều kiện | Mô tả |
|-----------|-------|
| `prev_route ≠ inferred_route` | Xe đổi tuyến |
| `prev_index - station_index ≥ 5` | Trạm nhảy lùi ≥ 5 bậc → xe quay vòng mới |
| `time_diff > 4200s` | Nghỉ > 70 phút |

**Luồng:**
1. Đọc `bus_station.json` → tạo bảng `(RouteID, StationName) → station_index`
2. Merge `station_index` vào GPS DataFrame
3. Dùng `shift(1)` so sánh trạm hiện tại vs trạm trước → phát hiện reset/đổi tuyến
4. Tạo `trip_id` mới bằng `cumsum`

---

### Bước 6 — Tính tốc độ trung bình (`calculate_derived_speed`)

**Công thức:** `avg_speed = (Haversine_distance / time_diff) × 3.6` (km/h)

**Luồng:**
1. `shift(1)` lấy tọa độ điểm trước trong cùng trip
2. Haversine vectorized (Numpy) → `distance_m`
3. `groupby().diff()` → `time_diff_sec`
4. `v = (s/t) × 3.6`, nếu `t ≤ 0` → `v = 0`

> Điểm đầu tiên mỗi trip có `avg_speed = 0` (không có điểm trước để tính).

---

### Bước 7 — Trích xuất Black Spot (`main` → query)

**Mục tiêu:** Tìm các điểm GPS đang kẹt xe thực sự (không phải dừng đón khách).

**5 điều kiện AND:**

| Điều kiện | Ngưỡng | Loại trừ |
|-----------|--------|----------|
| `speed < 5 km/h` | `station_stationary_speed_kmh` | Xe đứng yên |
| `avg_speed < 10 km/h` | `bottleneck_max_speed_kmh` | Đoạn đường tắc |
| `station_distance > 50m` | `jam_far_from_station_m` | Không phải tại trạm |
| `is_terminal == False` | — | Không phải bến xe đầu/cuối |
| `door_up == False AND door_down == False` | — | Không đang đón/trả khách |

> **Triết lý:** Xe dừng nhưng cửa đóng + xa trạm + không phải bến cuối = **kẹt xe**, không phải hoạt động bình thường.

---

## Config liên quan (`business_rules.yaml`)

| Key | Giá trị | Dùng ở bước |
|-----|---------|-------------|
| `station_distance_max_m` | 50 | Bước 1 (nén trạm) |
| `trip_split_max_gap_sec` | 4200 | Bước 2, 5 (phân chuyến) |
| `route_inference_min_support` | 0.6 | Bước 3 (FP-Growth) |
| `route_drift_threshold` | 0.5 | Bước 3 (drift detection) |
| `fpgrowth_explosion_threshold` | 20 | Bước 3 (anti-explosion) |
| `min_trips_per_segment` | 2 | Bước 3 (filter) |
| `min_stations_per_trip` | 2 | Bước 3 (filter) |
| `core_stations_min_count` | 2 | Bước 3 (filter) |
| `trip_resplit_drop_threshold` | 5 | Bước 5 (sequence reset) |
| `station_stationary_speed_kmh` | 5 | Bước 7 (black spot) |
| `bottleneck_max_speed_kmh` | 10 | Bước 7 (black spot) |
| `jam_far_from_station_m` | 50 | Bước 7 (black spot) |
| `earth_radius_m` | 6371000 | Bước 6 (Haversine) |

---

## Cách chạy

```bash
# Tiền điều kiện: Đã chạy xong Pipeline Silver
python pipelines/3.2_data_mining_gold.py
```

**Tiền điều kiện file:**
- `data/2_silver/bus_gps_data.parquet` ✅
- `data/2_silver/bus_station_data.json` ✅
- `data/1_bronze/bus_station.json` ✅ (dùng cho Bước 5)
- `config/business_rules.yaml` ✅

---

*Tham chiếu: [architecture.md](architecture.md) · [pipeline_sum.md](pipeline_sum.md)*
