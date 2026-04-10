# Black Spot — Phân tích Điểm đen Kẹt xe

> Tài liệu mô tả hệ thống phát hiện và trực quan hóa các "điểm đen" kẹt xe TP.HCM. Bao gồm: trích xuất dữ liệu kẹt xe từ pipeline Gold, phân cụm HDBSCAN, khai phá chuỗi lan truyền PrefixSpan, và dashboard bản đồ 3D tương tác.

---

## Tổng quan

```
dm_gold_data.parquet ──[dm_gold_pipeline.py]──→ black_spot.parquet ──→ [Dashboard 2_Black_Spot.py]
                                                                   ├── Tab 1: Bản đồ 3D Hexagon + HDBSCAN
                                                                   └── Tab 2: Arc Map hiệu ứng Domino
```

| Thành phần | File | Vai trò |
|-----------|------|---------|
| Trích xuất dữ liệu kẹt | `pipelines/dm_gold_pipeline.py` (hàm `main`) | Query 5 điều kiện → `black_spot.parquet` |
| Thuật toán phân tích | `app/utils.py` | HDBSCAN, PrefixSpan, Pydeck rendering |
| Dashboard | `app/pages/2_Black_Spot.py` | UI tương tác 2 tab |

---

## Phần 1: Trích xuất Black Spot (dm_gold_pipeline.py)

Ở cuối `main()` của `dm_gold_pipeline.py`, dữ liệu Gold đã gán tuyến được query với **5 điều kiện AND**:

| # | Điều kiện | Ngưỡng | Loại trừ trường hợp |
|---|-----------|--------|---------------------|
| 1 | `speed < 5 km/h` | `station_stationary_speed_kmh` | Xe đứng yên |
| 2 | `avg_speed < 10 km/h` | `bottleneck_max_speed_kmh` | Đoạn đường tắc |
| 3 | `station_distance > 50m` | `jam_far_from_station_m` | Không phải tại trạm |
| 4 | `is_terminal == False` | — | Không phải bến đầu/cuối |
| 5 | `door_up == False AND door_down == False` | — | Không đang đón/trả khách |

> **Triết lý:** Xe dừng + cửa đóng + xa trạm + không phải bến cuối = **kẹt xe thực sự**.

**Output:** `data/black_spot.parquet`

---

## Phần 2: Thuật toán (`app/utils.py`)

### 2.1 — HDBSCAN Clustering (`create_cluster`)

**Mục tiêu:** Gom các điểm kẹt xe rải rác thành **vùng kẹt** (cluster) có ý nghĩa.

**Luồng:**

1. Chuyển tọa độ GPS sang radian
2. Chạy `HDBSCAN(min_cluster_size, metric='haversine')`
3. Loại bỏ nhiễu (cluster = -1)
4. Tính tâm chấn mỗi cụm: `mean(x)`, `mean(y)`
5. Đếm severity = số điểm GPS trong cụm
6. Đặt tên cụm = trạm xe buýt gần nhất (Haversine distance)

**Tham số `min_cluster_size`:** Người dùng chỉnh trên sidebar (10-200, mặc định 50). Ý nghĩa: cần ít nhất bao nhiêu tín hiệu kẹt để công nhận là 1 vùng kẹt.

**Output:** DataFrame `cluster_centers` với các cột:

| Cột | Mô tả |
|-----|-------|
| `x`, `y` | Tọa độ tâm chấn |
| `Severity` | Số lượng GPS points trong cụm |
| `Cluster_Name` | `📍 Gần ngay tại trạm X` hoặc `⚠️ Cách trạm X 350m` |

### 2.2 — PrefixSpan Sequential Mining (`sequential_mining`)

**Mục tiêu:** Tìm các chuỗi kẹt xe lan truyền theo thời gian (ví dụ: "Zone_A kẹt rồi Zone_B cũng kẹt").

**Luồng:**

1. **Rời rạc hóa không gian:** `round(lat, 3)` + `round(lng, 3)` → tạo Zone ID (lưới ~100m × 100m)
2. **Xây chuỗi:** Gom `zone_id` theo `(vehicle, date)` → danh sách trình tự
3. **Deduplicate liên tiếp:** `[A, A, B, B, C]` → `[A, B, C]` (xe nhích trong cùng zone)
4. **PrefixSpan:** Tìm subsequences lặp ≥ `min_support = 20` lần (closed patterns)
5. Output: DataFrame `{Jam_Pattern, Frequency}` — ví dụ `Zone_10.816_106.601 -> Zone_10.815_106.603`

### 2.3 — Hậu xử lý PrefixSpan

| Hàm | Mô tả |
|-----|-------|
| `process_prefixspan_data` | Lọc pattern có `->` (lây lan), trích tọa độ source/target cho Arc Layer |
| `translate_prefixspan_patterns` | Dịch `Zone_10.816_106.601` → `[Bến xe Miền Đông]` bằng Haversine nearest station |

### 2.4 — Pydeck Rendering

#### `create_pydeck_3d_heatmap` — Bản đồ 3D (Tab 1)

3 layer chồng nhau:

| Layer | Kiểu | Dữ liệu | Mô tả |
|-------|------|----------|-------|
| 1 | `ScatterplotLayer` + `TextLayer` | `filtered_stations` | Trạm xe buýt (chấm xanh cyan + tên) |
| 2 | `HexagonLayer` | `filtered_df` | Cột 3D kẹt xe — cao = nhiều GPS kẹt, màu vàng→đỏ |
| 3 | `ScatterplotLayer` + `TextLayer` | `cluster_centers` | Tâm chấn HDBSCAN (vòng đỏ lớn + label vàng) |

- Camera pitch 50° (nhìn xiên), hỗ trợ zoom tự động khi click bảng Insights
- Tooltip style dark glassmorphism

#### `create_pydeck_arc_map` — Bản đồ Arc (Tab 2)

| Layer | Kiểu | Dữ liệu | Mô tả |
|-------|------|----------|-------|
| 1 | `ArcLayer` | `flow_df` | Cung đỏ→cam nối nguồn→đích, độ dày theo Frequency |
| 2 | `ScatterplotLayer` | `flow_df` | Chấm đỏ tại nguồn |
| 3 | `ScatterplotLayer` + `TextLayer` | `filtered_stations` | Trạm xe buýt |

- Camera tự zoom vào điểm giữa nếu chỉ có 1 arc được chọn

---

## Phần 3: Dashboard (`2_Black_Spot.py`)

### Sidebar — Bộ lọc

| Filter | Loại | Ghi chú |
|--------|------|---------|
| Khoảng ngày | date_input (range) | Xử lý edge case: user click 1 ngày → tuple 1 phần tử |
| Tuyến | multiselect | Lọc trước xe |
| Biển số xe | multiselect | Cascading: chỉ hiện xe thuộc tuyến đã chọn |
| Khung giờ | slider | Mặc định 6–19 |
| Min cluster size | slider | 10–200, mặc định 50 (HDBSCAN) |

### Tab 1 — Bản đồ "Điểm đen" kẹt xe

**Layout:** 70% bản đồ | 30% insights

**Bên trái — Bản đồ 3D:**
- Hexagon Layer hiển thị mật độ kẹt (cột 3D)
- Vòng đỏ HDBSCAN đánh dấu tâm chấn + label tên khu vực
- Camera bay tự động khi click bảng

**Bên phải — Insights:**
- Số lượng vùng kẹt phát hiện
- Bảng ranking: `Khu vực` + `Mức độ (Điểm GPS)` — **clickable** (click → camera zoom vào)
- Bảng top tuyến kẹt nhiều nhất

**Cơ chế click-to-zoom:**

```
User click dòng bảng → st.session_state.cluster_table
    → Đọc selected_rows[0] → Lấy tọa độ cluster
    → Cập nhật st.session_state.map_state → Camera zoom 15.5x
    → Bỏ click → Reset camera toàn thành phố
```

### Tab 2 — Bản đồ hiệu ứng Domino

**Layout:** 70% Arc Map | 30% bảng

**Bên trái — Arc Map:**
- Mặc định: Top 30 luồng lây lan nghiêm trọng nhất
- Sau click: Chỉ hiển thị luồng được chọn

**Bên phải — Bảng:**
- Cột `Luồng Lan Truyền` (đã dịch sang tên trạm) + `Số lần lặp lại`
- **Multi-row clickable** — click → bản đồ filter tương ứng
- Hỗ trợ đa chọn để so sánh nhiều luồng

**Minh họa bảng dịch:**

```
Zone_10.816_106.601 -> Zone_10.815_106.603
        ↓ translate_prefixspan_patterns()
[Bến xe Miền Đông] ➡️ [Ngã tư Hàng Xanh]
```

---

## Lưu ý Kỹ thuật

**Trạm xe buýt được lọc theo Regex:**
```python
# Tìm tuyến "1" mà không dính "10", "155", "91"
regex = r'\b1\b|\b50\b'  # word boundary
station_df['Routes'].str.contains(regex)
```

**Pydeck CARTO provider:** Dùng `map_provider="carto"` + `map_style="light"` — không cần API key (Mapbox/Google Maps).

**Dedup trạm:** `drop_duplicates(subset=['StopId'])` thay vì `Name` — vì nhiều trạm khác nhau có cùng tên.

---

## Cách chạy

```bash
# 1. Chạy pipeline (sẽ tạo black_spot.parquet cuối cùng)
python -m pipelines.dm_gold_pipeline

# 2. Chạy dashboard
streamlit run app/Dashboard.py
# → Chọn trang "Black Spot" trên sidebar
```

**Tiền điều kiện:**
- `data/black_spot.parquet` ✅ (output pipeline 3.2)
- `data/2_silver/bus_station_data.json` ✅ (tên trạm cho HDBSCAN + PrefixSpan)

---

*Tham chiếu: [data_mining_gold.md](data_mining_gold.md) · [architecture.md](architecture.md)*
