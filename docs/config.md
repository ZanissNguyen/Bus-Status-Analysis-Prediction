# Cấu hình Vận hành (`config/business_rules.yaml`)

> Tài liệu này chi tiết hóa các ngưỡng cấu hình (thresholds) được sử dụng xuyên suốt toàn bộ hệ thống. Đây là **Single Source of Truth (SSOT)** — mọi module từ pipeline đến dashboard đều phải đọc từ đây.

---

## 1. Ngưỡng Không gian (Spatial)

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `station_distance_max_m` | 50m | Bán kính để coi xe đã "đến trạm". Dùng để lọc điểm tại trạm trong Gold ML, Gold DM, và Bunching. |
| `silver_layer_max_distance_m` | 1000m | Khoảng cách tối đa từ trạm gần nhất để giữ lại điểm GPS ở tầng Silver (lọc nhiễu). |
| `jam_far_from_station_m` | 100m | Khoảng cách tối thiểu từ trạm để coi một điểm dừng là "kẹt xe" (black spot). |
| `geo_bounds` | [10.2, 11.3, 106.2, 107.1] | Bounding box địa lý của TP.HCM để loại bỏ các tọa độ GPS nhảy lỗi ra biển hoặc tỉnh khác. |

---

## 2. Ngưỡng Thời gian (Temporal)

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `bunching_threshold_mins` | 2.0 phút | Headway dưới ngưỡng này sẽ bị coi là dồn chuyến (bunching). |
| `gapping_threshold_mins` | 30.0 phút | Headway trên ngưỡng này sẽ bị coi là giãn chuyến/thủng tuyến (gapping). |
| `dwell_time_anomaly_max_mins` | 3.0 phút | Thời gian dừng tại trạm vượt quá ngưỡng này sẽ bị coi là nghẽn (bottleneck). |
| `new_session_gap_sec` | 600s | Khoảng thời gian trống giữa 2 ping GPS để tách session dừng đỗ (Bunching Pipeline). |
| `trip_split_max_gap_sec` | 1800s | Khoảng thời gian trống để tách chuyến (Trip Segmentation) trong Gold DM. |
| `trip_split_max_idle_sec` | 7200s | Thời gian đứng im tối đa (2h) để coi xe đang "ngủ đông" (bảo trì) và tách chuyến khi lăn bánh lại. |

---

## 3. Ngưỡng Tốc độ (Speed)

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `bottleneck_max_speed_kmh` | 10 km/h | Tốc độ trung bình đoạn đường dưới mức này được coi là ùn tắc. |
| `station_stationary_speed_kmh` | 5 km/h | Tốc độ tức thời dưới mức này được coi là xe đang đứng yên. |
| `max_realistic_speed_kmh` | 100 km/h | Tốc độ tối đa thực tế. Các ping GPS vượt quá mức này sẽ bị coi là lỗi sensor. |

---

## 4. Phân loại Tài xế (Driver Profiling)

Dựa trên quy tắc cứng (Hard Rules) thay thế cho K-Means để đảm bảo tính ổn định và tốc độ:

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `driver_violation_rate_pct` | 60.0% | Tỉ lệ mở cửa xa trạm (violation) để xếp vào nhóm **Violator**. |
| `driver_reckless_speed_std` | 13.0 | Độ lệch chuẩn tốc độ để xếp vào nhóm **Reckless** (phanh/ga gắt). |
| `driver_high_speed_kmh` | 20.0 km/h | Tốc độ trung bình để xếp vào nhóm **Speedster**. |

---

## 5. Khai phá Dữ liệu (Mining)

| Tham số | Giá trị | Mô tả |
|---------|---------|-------|
| `route_inference_min_support` | 0.6 | Độ tin cậy tối thiểu cho FP-Growth khi nhận diện tuyến xe. |
| `route_drift_threshold` | 0.5 | Tỉ lệ trùng khớp trạm để phát hiện xe đổi tuyến động (drift). |
| `domino_min_occurrences` | 3 | Số lần lặp lại tối thiểu của một chuỗi lỗi để coi là quy luật Domino. |
| `fpgrowth_explosion_threshold` | 15 | Giới hạn số lượng trạm phổ biến để tránh bùng nổ tổ hợp khi chạy FP-Growth. |

---

*Tham chiếu: [architecture.md](architecture.md) · [pipeline_detail.md](pipeline_detail.md)*
