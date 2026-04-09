# Phân tích Benchmark `max_gap_seconds` — Nên giảm từ 1800 không?

## 1. Kết quả từ Notebook

### Thuật toán tự động tìm ngưỡng

| Phương pháp | Ngưỡng tìm được | Ý nghĩa |
|---|---|---|
| **GMM** (2-cluster Gaussian Mixture) | **5.6 phút (337s)** | Ranh giới giữa "trễ nội bộ" (1.4p) và "nghỉ bến" (9.8p) |
| **KDE** (Kernel Density Estimation) | **18.3 phút (1100s)** | Đáy thung lũng trên phân phối thời gian trễ |

### Bảng Grid Search đầy đủ (3 chỉ số đánh giá)

| Ngưỡng (phút) | Xe gán tuyến | Avg Trips/xe | Avg Core Stations |
|---:|---:|---:|---:|
| **5.6** (GMM) | **420** ❌ | 134.4 | 19.7 |
| **15** | 453 | 125.7 | 22.7 |
| **18.3** (KDE) | 452 | 125.6 | 23.0 |
| **20** | **454** | 125.3 | 22.9 |
| 25 | 453 | 125.2 | 23.2 |
| **30** (hiện tại) | 453 | 124.3 | 23.7 |
| 35 | 453 | 123.9 | 24.0 |
| 40 | **454** | 123.1 | 24.2 |
| 45 | **454** | 122.6 | 24.5 |
| 50 | **454** | 122.3 | 24.6 |
| 55 | **454** | 122.1 | 24.6 |
| 60 | 453 | 122.0 | 24.7 |
| 65 | 453 | 121.8 | 24.7 |
| 70 | **454** | 121.3 | 24.6 |
| 75 | 452 | 120.2 | 24.5 |
| 80+ | 449-450 | ≤120 | ≤24.5 |

## 2. Cách đọc 3 chỉ số

| Chỉ số | Ý nghĩa | Mục tiêu |
|---|---|---|
| **Assigned Vehicles** | Số xe được gán thành công tuyến đường | **Càng cao càng tốt** (max = tổng số xe) |
| **Avg Trips** | Trung bình mỗi xe bị cắt ra bao nhiêu chuyến | **Không nên quá cao** (băm nát = mỗi chuyến quá ngắn, FP-Growth không đủ trạm) |
| **Avg Core Stations** | Trung bình số trạm lõi tìm được mỗi xe | **Càng cao càng tốt** (chuỗi trạm càng dài → nhận diện tuyến chính xác hơn) |

## 3. Phân tích chi tiết

### GMM = 5.6 phút → ❌ Không nên dùng
- Mất **34 xe** so với các ngưỡng khác (420 vs 454)
- Avg Trips = 134 → **băm nát** chuyến, mỗi chuyến quá ngắn
- Core Stations thấp nhất = 19.7 → FP-Growth không đủ dữ liệu để nhận diện tuyến
- **Lý do**: GMM bắt quá nhạy — mỗi lần xe dừng ở đèn đỏ lâu 6 phút đã coi là chuyến mới

### KDE = 18.3 phút → ⚠️ Khả dụng nhưng aggressive
- 452 xe — mất 2 xe so với max
- Avg Trips giảm nhẹ so với GMM → ít băm hơn
- Core Stations = 23.0 — ổn định

### Ngưỡng 20 phút → ✅ **Ứng viên tốt nhất nếu muốn giảm**
- **454 xe** — cao nhất bảng (tie với 40-55 phút)
- Avg Trips = 125.3 — cân bằng
- Core Stations = 22.9 — đủ cao để nhận diện tuyến chính xác

### Ngưỡng 30 phút (hiện tại) → ✅ Vẫn ổn
- 453 xe — chỉ kém 1 xe so với max
- Core Stations = 23.7 — **cao hơn** vùng 15-20 phút
- Vẫn nằm trong vùng "plateau" ổn định (20-70 phút)

### Ngưỡng ≥ 75 phút → ❌ Bắt đầu suy giảm
- Assigned Vehicles giảm (449-450)
- Chuyến bị gộp lại quá dài → pha trộn nhiều tuyến trong 1 chuyến

## 4. Kết luận & Khuyến nghị

> [!IMPORTANT]
> Dữ liệu cho thấy pipeline **không nhạy cảm** với `max_gap_seconds` trong khoảng **20–60 phút**.
> Cả 3 chỉ số đều nằm trong **"vùng plateau"** ổn định ở khoảng này.

### Hai lựa chọn hợp lý:

| Phương án | Giá trị | Lý do |
|---|---|---|
| **Giữ nguyên 1800s (30 phút)** | An toàn | Đã ổn định, Core Stations = 23.7 — cao hơn vùng thấp. Không cần đổi. |
| **Giảm xuống 1200s (20 phút)** | Tối ưu nhẹ | +1 xe gán tuyến, Avg Trips cân bằng hơn. Nhưng Core Stations giảm ~0.8. |

> [!TIP]
> **Trade-off cốt lõi**: Giảm ngưỡng = cắt nhiều chuyến hơn = mỗi chuyến ngắn hơn = ít trạm lõi hơn.
> Nhưng trong khoảng 20-30 phút, sự khác biệt rất nhỏ (~3% Core Stations).

### Kết luận cuối cùng:
**Giữ 1800s** nếu ưu tiên **độ ổn định** (production-ready).
**Đổi sang 1200s** nếu muốn **tối đa xe gán tuyến** và chấp nhận mất nhẹ Core Stations.

> [!WARNING]
> **KHÔNG** dùng ngưỡng GMM (337s). Nó cắt chuyến quá nhạy, làm băm nát dữ liệu.
