# Chi tiết Dashboard: Streamlit Multi-Page App

> Ứng dụng được thiết kế theo phong cách hiện đại với 4 trang chức năng chính, phục vụ từ giám sát tổng quan đến phân tích sâu các bài toán vận hành cụ thể.

---

## 1. Dashboard Tổng quan (Trang chủ)
**File:** `app/Dashboard.py`  
**Mục tiêu:** Cung cấp cái nhìn 30.000 feet cho quản lý cấp cao.

- **KPI Metrics:** Hiển thị 5 chỉ số sống còn (Operations Health, Bunching/Gapping %, Trip Count, Headway, Safe Driver %).
- **Driver Profiling (Hard Rules):** Phân loại tài xế thành 4 nhóm:
  - 🔴 **Violator:** Hay mở cửa xa trạm (vi phạm an toàn).
  - 🟠 **Speedster:** Lái nhanh nhưng ổn định.
  - 🟡 **Reckless:** Tốc độ thay đổi đột ngột (phanh/ga gắt).
  - 🟢 **Safe:** Lái xe an toàn theo chuẩn.
- **Deep-dive Tabs:** Bảng xếp hạng các tuyến tệ nhất dựa trên tổng tỉ lệ lỗi vận hành.

---

## 2. Dự báo Thời Gian (Predict Duration)
**File:** `app/pages/1_Predict_Duration.py`  
**Mục tiêu:** So sánh hiệu năng của các mô hình ML.

- **Mô hình:** Tích hợp 3 mô hình (Linear Regression, Random Forest, Gradient Boosting).
- **Tính năng:** Người dùng chọn cặp trạm và khung giờ → App tự tra cứu khoảng cách lịch sử và thực hiện inference.
- **Trực quan:** Biểu đồ Bar so sánh kết quả dự báo của 3 model cùng thời gian trung bình lịch sử.

---

## 3. Bản đồ Điểm Đen (Black Spot)
**File:** `app/pages/2_Black_Spot.py`  
**Mục tiêu:** Nhận diện các điểm nóng ùn tắc.

- **3D Hexagon Map:** Hiển thị mật độ kẹt xe dưới dạng các cột 3D.
- **HDBSCAN Clustering:** Tự động gom nhóm các điểm kẹt đơn lẻ thành "Vùng kẹt xe" và gắn nhãn theo tên trạm gần nhất.
- **Drill-down Table:** Danh sách các vùng kẹt xe nghiêm trọng nhất. Click vào dòng bất kỳ → Camera bản đồ tự động "bay" (flyTo) đến vị trí đó.
- **Domino Flow Map:** Arc layer hiển thị hướng lan truyền của kẹt xe theo chuỗi thời gian (Sequential Pattern Mining).

---

## 4. Hiệu năng Vận hành (Transit Performance)
**File:** `app/pages/3_Transit_Performance.py`  
**Mục tiêu:** Phân tích dồn chuyến và thủng tuyến.

- **Heatmap Matrix:** Ma trận nhiệt hiển thị tỉ lệ Bunching/Gapping theo Trạm (trục Y) và Giờ (trục X).
- **Trục Y Địa Lý:** Trạm được sắp xếp chính xác theo lộ trình (Outbound/Inbound) thay vì xếp tên ABC, giúp dễ dàng nhận diện lỗi lan truyền dọc tuyến.
- **Domino Tracking:** Hiển thị các chuỗi lỗi liên hoàn (ví dụ: A kẹt kéo theo B dồn chuyến). Hỗ trợ tìm kiếm theo tên trạm để truy vết nguồn gốc sự cố.

---

*Tham chiếu: [dashboard.md](dashboard.md) · [architecture.md](architecture.md)*
