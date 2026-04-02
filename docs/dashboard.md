# Dashboard Tổng quan Vận hành (`app/Dashboard.py`)

> Trang chính (entry point) của ứng dụng Streamlit — bảng điều khiển tổng hợp KPI, xu hướng, và phân tích chi tiết phục vụ C-Level. Được thiết kế theo kiến trúc **Top → Down**: KPI → Trends → Deep-Dive.

---

## Tổng quan

**Entry point:** `streamlit run app/Dashboard.py`
**Layout:** `wide` (full-width)
**Dependency dữ liệu:** 4 schema

```
┌──────────────────────────────────────────────────────────────────┐
│                   SIDEBAR: Bộ Lọc Toàn Cục                      │
│  Tuyến (multiselect) · Khoảng ngày (date_input range)           │
├──────────────────────────────────────────────────────────────────┤
│  TẦNG 1: KPIs (5 metric cards hàng ngang)                       │
│  %Normal | %B+G | Số chuyến | Headway TB | %Tài xế an toàn     │
├──────────────────────────────────────────────────────────────────┤
│  TẦNG 2: Trends (2 cột)                                         │
│  [Stacked Bar: Bottleneck/Bunching/Gapping theo giờ]            │
│  [Tab: Tốc độ TB theo giờ | Dwell Time theo giờ]               │
├──────────────────────────────────────────────────────────────────┤
│  TẦNG 3: Deep-Dive (4 tabs)                                     │
│  [Tab 1: Bảng xếp hạng tuyến]                                  │
│  [Tab 2: Ma trận nhiệt tốc độ cặp trạm]                       │
│  [Tab 3: Bảng trạm thường xuyên lỗi]                           │
│  [Tab 4: Bảng đánh giá tài xế]                                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4 Schema dữ liệu đầu vào

| # | Schema | File | Dùng cho |
|---|--------|------|----------|
| 1 | GPS Silver | `2_silver/bus_gps_data.parquet` | Dữ liệu GPS gốc + driver profiling |
| 2 | Trip Gold | `3_gold/dm_gold_data.parquet` | Tốc độ TB, trip_id, inferred_route |
| 3 | ML Gold | `3_gold/ml_gold_data.parquet` | distance/duration → segment speed heatmap |
| 4 | Reliability | `bunching.csv` | Headway, dwell_time, bunching/gapping flags |

### Cơ chế Synthetic Fallback

Nếu bất kỳ file nào **thiếu** hoặc có **< 50 dòng**, Dashboard tự sinh dữ liệu giả (synthetic) với schema giống hệt để UI không crash:

```python
try:
    df = pd.read_parquet(path)
    if len(df) < 50: raise ValueError
except:
    df = generate_schema_X()  # Sinh dữ liệu ngẫu nhiên cùng schema
```

> **Tại sao cần Fallback?** Dashboard là trang trình bày cho C-Level — crash app = thảm họa. Synthetic data đảm bảo mọi biểu đồ luôn render được, kể cả khi pipeline chưa chạy xong.

---

## Sidebar — Bộ Lọc Toàn Cục

| Filter | Loại | Ảnh hưởng |
|--------|------|-----------|
| Tuyến | multiselect | Lọc Schema 2 (trip) + Schema 4 (reliability) |
| Khoảng ngày | date_input (range) | Lọc tất cả schema theo `date` |

Xử lý edge case: tuple 1 phần tử khi user mới click ngày bắt đầu, `NaN` min/max date.

---

## Tầng 1: KPIs (5 thẻ metric)

| # | KPI | Công thức | Delta |
|---|-----|-----------|-------|
| 1 | Chỉ số vận hành | `%Normal / Total` (từ Schema 4) | So với target `80%` |
| 2 | % Bunching + Gapping | `(B + G) / Total × 100` | Chi tiết `B: x% \| G: y%` |
| 3 | Số chuyến | `trip_id.nunique()` | — |
| 4 | Headway TB | `headway_mins.mean()` (phút) | — |
| 5 | % Tài xế an toàn | Hard Rules profiling (xem bên dưới) | Cảnh báo nếu < `75%` |

### Driver Profiling — Hard Rules (KPI #5)

Thay vì chạy K-Means (chậm + không deterministic), dashboard dùng **3 quy tắc cứng** từ config:

```
1. violation_rate ≥ 60% → "Violator" (mở cửa xa trạm quá nhiều)
2. speed_mean ≥ 13 hoặc speed_std ≥ 13 → "Reckless" (lái dao động)
3. avg_speed_mean ≥ 20 → "Speedster" (chạy nhanh nhưng ổn định)
4. Còn lại → "Safe"
```

**Lưu ý quan trọng:** Speed = 0 hoặc âm bị ép thành `NaN` trước khi tính `.mean()` / `.std()` — đảm bảo chỉ đo tốc độ "khi đang chạy", không bị GPS nhiễu kéo tụt.

---

## Tầng 2: Trends (2 cột)

### Cột trái — Stacked Bar: Tần suất lỗi theo giờ

- Gom `is_bottleneck`, `is_bunching`, `is_gapping` theo `hour` → `sum()`
- Melt wide→long → Stacked bar chart
- Màu: Orange (Bottleneck), Red (Bunching), Black (Gapping)

### Cột phải — 2 tab con

| Tab | Dữ liệu | Biểu đồ |
|-----|----------|---------|
| Tốc độ di chuyển | Schema 2, lọc `avg_speed > 0` | Line chart (Emerald) |
| Độ trễ tại trạm | Schema 4, `dwell_time_mins` | Line chart (Violet) |

---

## Tầng 3: Deep-Dive (4 tabs)

### Tab 1 — Bảng xếp hạng tuyến

- Gom `is_bottleneck`, `is_bunching`, `is_gapping` theo `inferred_route`
- Tính `%` mỗi loại = `count_error / total_stops × 100`
- **Bad_Score** = tổng 3 % → sort giảm dần (tuyến tệ nhất lên đầu)
- Gradient `Reds` trên 3 cột %

### Tab 2 — Ma trận nhiệt tốc độ cặp trạm

- Tính `segment_speed_kmh = (distance / duration) × 3.6` từ Schema 3
- **Proxy Filter:** Schema 3 không có cột tuyến → lọc gián tiếp bằng danh sách trạm từ Schema 4
- Nếu > 20 cặp trạm → chỉ hiện **Top 20 chậm nhất** (bottleneck segments)
- Heatmap `RdYlGn`: đỏ = chậm (nguy hiểm), xanh = nhanh (an toàn)

### Tab 3 — Bảng trạm thường xuyên lỗi

- Gom 3 loại lỗi theo `current_station`
- `Total_Errors = Bottleneck + Bunching + Gapping`
- Lọc `Total_Errors > 0` → sort ascending
- Gradient `YlOrRd`

### Tab 4 — Bảng đánh giá tài xế

- Dùng kết quả `d_agg` từ KPI #5 (driver profiling)
- Hiển thị: tài xế, % mở cửa xa trạm, tốc độ TB, dao động, phân loại
- **Color-coded Profile:** Đỏ (Violator), Cam (Speedster), Vàng (Reckless), Xanh (Safe)
- Sort: Violator → Speedster → Reckless → Safe

---

## Config liên quan (`business_rules.yaml`)

| Key | Giá trị | Dùng ở |
|-----|---------|--------|
| `station_distance_max_m` | 50 | Driver violation: mở cửa xa trạm |
| `driver_violation_rate_pct` | 60 | Ngưỡng "Violator" |
| `driver_reckless_speed_std` | 13 | Ngưỡng "Reckless" |
| `driver_high_speed_kmh` | 20 | Ngưỡng "Speedster" |
| `service_health_target_pct` | 80 | KPI target %Normal |
| `safe_driver_alert_pct` | 75 | Cảnh báo nếu < 75% safe |

---

## Cách chạy

```bash
# Tiền điều kiện: Đã chạy ít nhất pipeline Silver + Gold + Bunching
streamlit run app/Dashboard.py
```

> Dashboard vẫn hoạt động kể cả khi thiếu file nhờ cơ chế Synthetic Fallback, nhưng dữ liệu sẽ là **giả** — không phản ánh thực tế.

**Pages con (Streamlit multi-page):**

| Trang | File | Tài liệu tham chiếu |
|-------|------|---------------------|
| Predict Duration | `pages/1_Predict_Duration.py` | [machine_learning_gold.md](machine_learning_gold.md) |
| Black Spot | `pages/2_Black_Spot.py` | [back_spot.md](back_spot.md) |
| Transit Performance | `pages/3_Transit_Performance.py` | [bunching.md](bunching.md) |

---

*Tham chiếu: [architecture.md](architecture.md) · [pipeline_sum.md](pipeline_sum.md)*
