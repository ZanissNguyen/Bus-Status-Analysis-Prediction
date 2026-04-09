# Pipeline Bunching & Gapping + Dashboard Transit Performance

> Pipeline phân tích bunching (dồn xe), gapping (thủng tuyến), dwell time (thời gian trễ tại trạm), và hiệu ứng domino (lây lan lỗi). Kết quả được trực quan hóa trên trang `3_Transit_Performance.py`.

---

## Tổng quan

```
dm_gold_data.parquet ──→ [bunching_pipeline.py] ──→ bunching.parquet + domino_rules.parquet
                                                      │
                                                      ▼
                                          [Dashboard 3_Transit_Performance.py]
                                          ├── Tab 1: Heatmap Bunching/Gapping
                                          ├── Tab 2: So sánh 100% Stacked Bar
                                          └── Tab 3: Chuỗi Domino lây lan
```

| Output | Mô tả |
|--------|-------|
| `data/bunching.parquet` | Bảng stop events với cờ bunching/gapping/bottleneck |
| `data/domino_rules.parquet` | Các chuỗi lỗi liên hoàn (domino chains) lặp lại ≥ 3 lần |

---

## Phần 1: Pipeline (`bunching_pipeline.py`)

**Input:** `data/3_gold/dm_gold_data.parquet` (output của pipeline 3.2)

### Bước 1 — Lọc sự kiện tại trạm

Giữ lại bản ghi GPS thỏa **tất cả** điều kiện:

| Điều kiện | Mô tả |
|-----------|-------|
| `station_distance ≤ 50m` | Nằm trong bán kính trạm |
| `door_up OR door_down OR speed < 5 OR avg_speed < 10` | Đang dừng hoặc di chuyển chậm |
| `is_terminal == False` | Không phải bến đầu/cuối (tránh false positive) |

### Bước 2 — Sessionization (Phân lượt dừng)

Gom các bản ghi GPS liên tiếp cùng xe + cùng trạm thành **1 lượt dừng (stop session)**:

- Khoảng cách thời gian > `new_session_gap_sec = 600s` (10 phút) → lượt dừng mới
- Output: cột `stop_session_id` (rolling ID)

### Bước 3 — Tính Dwell Time

Gom nhóm theo `(route, station, vehicle, session, trip)`:

```
dwell_time_mins = (departure_time - arrival_time) / 60
```

Mỗi row output = **1 sự kiện dừng đỗ** tại 1 trạm, với thời gian đến và đi.

### Bước 4 — Tính Headway

Headway = khoảng cách thời gian giữa 2 xe liên tiếp đến cùng 1 trạm trên cùng 1 tuyến:

```
headway_mins = (arrival_time_xe_B - arrival_time_xe_A) / 60
```

Sort theo `(route, station, arrival_time)` → `shift(1)` lấy thời gian xe trước.

Headway > `night_break_headway_mins = 180 phút` → gán NaN (nghỉ đêm, không tính).

### Bước 5 — Gán cờ (Flagging)

| Cờ | Điều kiện | Ngưỡng |
|----|-----------|--------|
| `is_bunching` | `headway ≤ 2 phút` | Hai xe đến quá sát nhau → dồn xe |
| `is_gapping` | `headway ≥ 30 phút` | Hành khách chờ quá lâu → thủng tuyến |
| `is_bottleneck` | `dwell_time ≥ 3 phút` | Trạm bị nghẽn (xe dừng quá lâu) |

**service_status** (ưu tiên): `Bunching` > `Gapping` > `Normal` (dùng `np.select`)

### Bước 6 — Khai phá Domino (`mine_domino_effects`)

**Mục tiêu:** Tìm các chuỗi lỗi liên hoàn — ví dụ: "Nếu trạm A bị Bunching, trạm B và C kế tiếp cũng bị."

**Logic:**

1. **Phân loại trạng thái domino:** `Bunching`, `Gapping`, `Bottleneck`, hoặc `Normal`
2. **Xác định block liên tiếp:** Chain đứt khi gặp `Normal`, đổi trip, hoặc đổi xe
3. **Gom chuỗi lỗi:** Mỗi block lỗi liên tiếp → 1 chuỗi domino (ví dụ: `Bunching_TrạmA ➔ Bottleneck_TrạmB ➔ Gapping_TrạmC`)
4. **Lọc:**
   - Chỉ giữ chuỗi có ≥ `domino_min_chain_length = 2` trạm
   - Chỉ giữ chuỗi lặp lại ≥ `domino_min_occurrences = 3` lần

**Output:** `domino_rules.parquet` — 3 cột:

| Cột | Mô tả |
|-----|-------|
| `Dây chuyền Domino (Sequence)` | Chuỗi lỗi: `Bunching_A ➔ Bottleneck_B ➔ ...` |
| `Độ dài Chuỗi lây lan (Trạm)` | Số trạm liên tiếp bị ảnh hưởng |
| `Số lần lặp lại (Occurrences)` | Bao nhiêu lần chuỗi này xảy ra |

---

## Phần 2: Dashboard (`3_Transit_Performance.py`)

### Sidebar — Bộ lọc

| Filter | Loại | Ghi chú |
|--------|------|---------|
| Ngày | date_input | 1 ngày cụ thể |
| Tuyến | selectbox | Tuyến duy nhất |
| Chiều chạy | radio | Outbound / Inbound |
| Khung giờ | slider | 0–23 (mặc định 5–22) |
| Biển số xe | multiselect | Tùy chọn, lọc sau cùng |

### Tab 1 — Heatmap Bunching & Gapping

**2 bảng nhiệt cạnh nhau:**

| Bảng | Trục X | Trục Y | Giá trị | Bảng màu |
|------|--------|--------|---------|----------|
| Bunching | Giờ (0-23) | Trạm (theo thứ tự tuyến) | % bunching | Reds 🔴 |
| Gapping | Giờ (0-23) | Trạm (theo thứ tự tuyến) | % gapping | Blues 🔵 |

**Xử lý trục Y quan trọng:**

- Thứ tự trạm lấy từ `bus_station.json` (master topology), **không** sắp ABC
- Chuẩn hóa Unicode NFC cho tiếng Việt (chống bất đồng bộ `ă` vs `ă`)
- Chỉ hiển thị trạm có data point (compact axis) nhưng vẫn giữ đúng thứ tự địa lý
- `autorange="reversed"` → trạm đầu tuyến ở trên, trạm cuối ở dưới

### Tab 2 — So sánh tuyến (100% Stacked Bar)

- Gom **tất cả tuyến** trong ngày + khung giờ đã chọn
- Tính % Normal / Bunching / Gapping cho mỗi tuyến
- Vẽ 100% stacked bar: Xanh (Normal), Đỏ (Bunching), Đen (Gapping)
- Label % hiển thị bên trong mỗi thanh

### Tab 3 — Chuỗi Domino

- Đọc `domino_rules.parquet` (output `bunching_pipeline.py`)
- Hỗ trợ **tìm kiếm text** theo tên trạm (case-insensitive)
- Layout 2 cột:
  - **Trái:** Horizontal bar chart Top 15 chuỗi domino nguy hiểm nhất (màu gradient Reds)
  - **Phải:** DataFrame full-list với gradient `OrRd` trên cột occurrences
- Nếu chuỗi domino > 2 nút → rút ngắn bằng `...` trên biểu đồ (tooltip hiện đủ)

---

## Config liên quan (`business_rules.yaml`)

| Key | Giá trị | Dùng ở |
|-----|---------|--------|
| `station_distance_max_m` | 50 | Bước 1 (lọc tại trạm) |
| `station_stationary_speed_kmh` | 5 | Bước 1 (xe đứng yên) |
| `bottleneck_max_speed_kmh` | 10 | Bước 1 (di chuyển chậm) |
| `new_session_gap_sec` | 600 | Bước 2 (sessionization) |
| `dwell_time_anomaly_max_mins` | 3.0 | Bước 5 (bottleneck) |
| `bunching_threshold_mins` | 2.0 | Bước 5 (bunching) |
| `gapping_threshold_mins` | 30.0 | Bước 5 (gapping) |
| `night_break_headway_mins` | 180.0 | Bước 4 (loại nghỉ đêm) |
| `domino_min_chain_length` | 2 | Bước 6 (độ dài tối thiểu) |
| `domino_min_occurrences` | 3 | Bước 6 (lọc nhiễu) |

---

## Cách chạy

```bash
# Tiền điều kiện: Đã chạy pipeline 3.2 (Data Mining Gold)
python -m pipelines.bunching_pipeline

# Sau đó chạy Dashboard
streamlit run app/Dashboard.py
# → Chọn trang "Transit Performance" trên sidebar
```

**Tiền điều kiện file:**
- `data/3_gold/dm_gold_data.parquet` ✅ (output pipeline 3.2)
- `data/1_bronze/bus_station.json` ✅ (dùng cho trục Y heatmap)
- `data/2_silver/bus_station_data.json` ✅ (dùng cho station metadata)

---

*Tham chiếu: [data_mining_gold.md](data_mining_gold.md) · [architecture.md](architecture.md)*
