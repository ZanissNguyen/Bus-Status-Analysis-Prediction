# Sử dụng bản slim: Cân bằng hoàn hảo giữa dung lượng siêu nhỏ và độ tương thích thư viện
FROM python:3.10-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Khai báo biến môi trường giúp Python chạy mượt hơn trong Docker
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy file requirements vào trước (Tận dụng Docker Layer Cache để build nhanh hơn ở các lần sau)
COPY requirements.txt .

# Cài đặt thư viện thuần túy qua pip wheels
# Lệnh --no-cache-dir cực kỳ quan trọng: Nó xóa các file nén tạm thời sau khi cài xong, giúp giảm đáng kể size image
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào container
COPY . .

# Mở port cho Streamlit
EXPOSE 8501

# Lệnh khởi chạy
CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]