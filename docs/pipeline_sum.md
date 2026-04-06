# Pipeline Tóm tắt: Raw → Bronze → Silver

> Bản tóm gọn của [pipeline_detail.md](pipeline_detail.md). Đọc file chi tiết nếu cần hiểu sâu từng bước.

---

## Tổng quan

Dữ liệu GPS xe buýt TP.HCM đi qua **3 pipeline tuần tự** trước khi sẵn sàng phân tích:

```
[API eBMS] ──crawl──→ bus_station.json ─┐
                                        ├──→ [Silver] bus_gps_data.parquet
[85 JSON] ──bronze──→ data_raw.parquet ─┘         + bus_station_data.json
```

| # | Script | Input | Output | Ghi chú |
|---|--------|-------|--------|---------|
| 0 | `crawl_bus_station.py` | API eBMS (29 tuyến) | `1_bronze/bus_station.json` | Chạy 1 lần, cần trình duyệt |
| 1 | `1_bronze.py` | `bus_gps/sub_raw_104→188.json` | `1_bronze/data_raw.parquet` | Gộp 85 file JSON → 1 Parquet |
| 2 | `2_silver.py` | Output Pipeline 0 + 1 | `2_silver/bus_gps_data.parquet` + `bus_station_data.json` | Làm sạch + gán trạm |

---

## Pipeline 0 — Crawl Trạm (`crawl_bus_station.py`)

**Vấn đề:** API eBMS bị Cloudflare chặn → không gọi `requests` được.
**Giải pháp:** Dùng `DrissionPage` (headless Chromium) mở trình duyệt thật, rồi `run_js(fetch())` bên trong context đã bypass.

**Luồng:**
1. Duyệt qua 29 route ID hardcode
2. Gọi `getvarsbyroute/{id}` → lấy metadata (mã tuyến, variant Outbound/Inbound)
3. Gọi `getstopsbyvar/{id}/{var}` → lấy danh sách trạm (StopId, Name, Lat, Lng)
4. Bổ sung thủ công 2 tuyến thiếu trên API: `70-5`, `61-7`
5. Lưu → `data/1_bronze/bus_station.json`

---

## Pipeline 1 — Bronze (`1_bronze.py`)

**Mục tiêu:** 85 file JSON → 1 file Parquet (nhanh ~10x, nhỏ ~3-5x so với JSON).

**Luồng:**
1. Đọc từng file `sub_raw_{i}.json`, trích `msgBusWayPoint` từ mỗi bản ghi
2. *(Tùy chọn)* Stratified sampling: chia 8 bin thời gian, lấy mẫu đều → dùng `SCALE=0.1` cho dev, `SCALE=1` cho prod
3. `pd.concat()` tất cả → lưu `data_raw.parquet`

**Schema Bronze (11 cột):** `vehicle`, `datetime` (unix), `x`, `y`, `speed`, `door_up/down`, `heading`, `aircon`, `working`, `ignition`

> ⚠️ Dữ liệu Bronze **chưa sạch**: door có thể NaN, tọa độ có thể văng, có trùng lặp.

---

## Pipeline 2 — Silver (`2_silver.py`)

**Mục tiêu:** Biến Bronze thô → dataset sạch + gán trạm gần nhất (BallTree).

### Bước 1: Làm sạch GPS (`clean_bus_gps_data`) — 6 phép lọc tuần tự

| # | Thao tác | Mô tả |
|---|----------|-------|
| 1 | Drop cột thừa | Xóa `heading`, `aircon`, `working`, `ignition` |
| 2 | Unix → realtime | Thêm cột `realtime` dạng chuỗi `dd-MM-yyyy HH:mm:ss` (giữ `datetime` gốc) |
| 3 | Khử trùng lặp | Key: `(vehicle, datetime)` → sort theo xe + thời gian |
| 4 | Fill NaN + Cast | `speed→0.0`, `door_up/down→False` (fill `0` trước, cast `bool` sau → tránh FutureWarning) |
| 5 | Drop tọa độ NaN | Xóa bản ghi thiếu `x` hoặc `y` |
| 6 | Bounding Box | Lọc `10.2≤y≤11.3`, `106.2≤x≤107.1` (bỏ GPS văng khỏi TP.HCM) |

### Bước 2: Chuẩn hóa Trạm

- Flatten `bus_station.json`: nested `[{Stations: [...]}]` → danh sách phẳng
- Gán `is_terminal = True` cho trạm đầu/cuối tuyến (tránh false positive bunching)
- Rename `Lat→y`, `Lng→x` để khớp convention GPS DataFrame

### Bước 3: Spatial Join (`map_bus_to_station`) — BallTree

1. Chuyển tọa độ GPS + trạm sang **radian**
2. Xây `BallTree(station_coords, metric='haversine')` trên tập trạm
3. Query `k=1` nearest neighbor cho ~N triệu điểm GPS → `O(N × log(M))`
4. Chuyển khoảng cách: `radian × 6,371,000 = mét`
5. Gán 3 cột mới: `current_station`, `station_distance`, `is_terminal`
6. **Lọc:** Giữ điểm GPS có `station_distance < 1000m`

> **1000m vs 50m:** Silver giữ 1000m để không mất dữ liệu xe di chuyển giữa các trạm. Ngưỡng 50m ("tại trạm") chỉ áp dụng ở Gold.

---

## Schema Silver (Output cuối)

### `bus_gps_data.parquet` — 11 cột

| Cột | Kiểu | Nguồn |
|-----|------|-------|
| `vehicle` | string | Bronze |
| `datetime` | int64 | Bronze (unix) |
| `x`, `y` | float64 | Bronze (kinh/vĩ độ) |
| `speed` | float64 | Bronze (NaN→0.0) |
| `door_up`, `door_down` | bool | Bronze (NaN→False) |
| `realtime` | string | Derived (`dd-MM-yyyy HH:mm:ss`) |
| `current_station` | string | BallTree (tên trạm gần nhất) |
| `station_distance` | float64 | BallTree (khoảng cách mét) |
| `is_terminal` | bool | BallTree (trạm đầu/cuối tuyến) |

### `bus_station_data.json` — 8 cột

`StopId`, `Code`, `Name`, `StopType`, `y`, `x`, `Routes`, `is_terminal`

---

## Cách chạy

```bash
python pipelines/crawl_bus_station.py   # Bước 0 (1 lần)
python pipelines/1_bronze.py            # Bước 1
python pipelines/2_silver.py            # Bước 2
```

**Lỗi thường gặp:**

| Lỗi | Sửa |
|-----|-----|
| `PathNotFoundError: bus_station.json` | Chạy `crawl_bus_station.py` trước |
| `PathNotFoundError: data_raw.parquet` | Chạy `1_bronze.py` trước |
| `MemoryError` ở Bronze | Giảm `SCALE` xuống `0.1` |
| `ConfigLoadError` | Kiểm tra `config/business_rules.yaml` |

---

## Config liên quan (`config/business_rules.yaml`)

| Key | Giá trị | Dùng ở |
|-----|---------|--------|
| `geo_bounds.*` | `10.2–11.3 / 106.2–107.1` | Silver bước 6 |
| `silver_layer_max_distance_m` | `1000` | Silver bước BallTree |
| `earth_radius_m` | `6371000.0` | Chuyển radian→mét |

---

*Xem chi tiết đầy đủ tại [pipeline_detail.md](pipeline_detail.md). Tham chiếu kiến trúc: [architecture.md](architecture.md).*
