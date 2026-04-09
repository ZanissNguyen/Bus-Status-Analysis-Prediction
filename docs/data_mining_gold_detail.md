# Chi tiết Thuật toán: Gold Data Mining

> Tài liệu này đi sâu vào các giải pháp kỹ thuật phức tạp trong `dm_gold_pipeline.py`, đặc biệt là thuật toán **Dynamic Drift Tracking** để nhận diện tuyến xe và **FP-Growth** để xác định lộ trình.

---

## 1. Thách thức: Xe chạy đa tuyến
Dữ liệu GPS thô không đi kèm mã tuyến (RouteID). Hơn nữa, một xe buýt có thể chạy nhiều tuyến khác nhau trong một ngày (ví dụ: sáng chạy tuyến 50, chiều chạy tuyến 56). 

**Giải pháp:** Chia nhỏ lịch trình của xe thành các đoạn (segments) dựa trên sự thay đổi tập hợp các trạm dừng.

---

## 2. Dynamic Drift Tracking (Nhận diện Đổi tuyến)

Thay vì cố định một tuyến cho cả ngày, chúng tôi duy trì một **Memory Pool** (Bể nhớ) chứa các trạm đã đi qua trong cửa sổ trượt:

1. **Overlap Ratio:** Với mỗi chuyến đi (trip) mới, tính tỷ lệ trạm của chuyến đó đã từng xuất hiện trong Bể nhớ.
   $$Overlap = \frac{Stations_{new} \cap MemoryPool}{Stations_{new}}$$
2. **Drift Detection:** Nếu $Overlap < 0.5$ (ngưỡng `route_drift_threshold`), xe được coi là đã đổi sang một tuyến mới hoàn toàn.
3. **Segmentation:** Khi phát hiện Drift, pipeline sẽ chốt đoạn dữ liệu cũ, chạy nhận diện tuyến cho đoạn đó, và khởi tạo một Bể nhớ mới cho đoạn tiếp theo.

---

## 3. Nhận diện tuyến bằng FP-Growth

Sau khi có một đoạn dữ liệu (segment) gồm nhiều chuyến đi, chúng tôi tìm "Tuyến đường phù hợp nhất":

1. **Transaction Encoding:** Mỗi chuyến đi được coi là một "giỏ hàng", các trạm dừng là "mặt hàng".
2. **FP-Growth:** Tìm tập hợp các trạm (itemsets) xuất hiện thường xuyên nhất (support > 0.6).
3. **Majority Voting:** 
   - Với mỗi trạm trong tập phổ biến nhất, tra cứu xem trạm đó thuộc về những tuyến nào (từ `bus_station.json`).
   - Tuyến nào có số lượng trạm xuất hiện nhiều nhất trong tập phổ biến sẽ được chọn làm `inferred_route`.

---

## 4. Tách chuyến theo cấu trúc Tuyến (Re-splitting)

Mặc dù đã tách chuyến sơ bộ bằng thời gian nghỉ, nhưng để phân tích Bunching chính xác, chuyến đi phải được cắt theo đúng chu kỳ lộ trình:

- **Station Indexing:** Đánh số thứ tự trạm (0, 1, 2...) theo topology của tuyến đã nhận diện.
- **Sequence Reset Index:** Nếu trạm hiện tại có index nhỏ hơn trạm trước đó đáng kể (ví dụ xe đang ở trạm cuối [index 30] rồi nhảy về trạm đầu [index 2]) → Xe đã quay vòng bến → Cắt chuyến mới.

---

## 5. Trích xuất Black Spot (Điểm đen kẹt xe)

Thuật toán lọc kẹt xe dựa trên sự phối hợp giữa 5 tín hiệu:
- **Tín hiệu Tĩnh:** Tốc độ tức thời < 5km/h.
- **Tín hiệu Động:** Tốc độ trung bình đoạn đường < 10km/h (loại trừ trường hợp xe chỉ dừng đèn đỏ chớp nhoáng).
- **Tín hiệu Không gian:** Cách trạm > 50m (loại trừ trường hợp xe đang đón khách tại trạm).
- **Tín hiệu Vận hành:** Cửa đóng (door_up/down = False) và không phải ở bến cuối.

---

*Tham chiếu: [data_mining_gold.md](data_mining_gold.md) · [architecture.md](architecture.md)*
