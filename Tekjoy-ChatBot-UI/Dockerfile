# --- Dockerfile ---
FROM python:3.11-slim

# Đặt thư mục làm việc trong container (tùy ý, không cần /app)
WORKDIR /Tekjoy-ChatBot-UI

# Tạo môi trường ảo
RUN python -m venv /venv

# Copy file requirements.txt và cài đặt dependencies
COPY requirements.txt .
RUN /venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code frontend
COPY . .

# Thêm venv vào PATH
ENV PATH="/venv/bin:$PATH"

# Mở port frontend
EXPOSE 3000

# Chạy ứng dụng (FastAPI server)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
