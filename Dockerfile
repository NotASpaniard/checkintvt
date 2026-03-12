# Sử dụng Python image chính thức (bản slim để nhẹ)
FROM python:3.9-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Cài đặt các thư viện hệ thống cần thiết cho psycopg2 (nếu dùng bản binary thì có thể không cần nhưng nên có)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements và cài đặt dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào container
COPY . .

# Railway sẽ tự động cung cấp biến PORT, nhưng Flask mặc định chạy 5000
EXPOSE 5000

# Lệnh khởi chạy ứng dụng bằng Gunicorn (phù hợp cho production)
# 4 workers để xử lý 100+ người dùng đồng thời
CMD ["gunicorn", "app:application", "--workers", "4", "--bind", "0.0.0.0:5000", "--timeout", "120"]
