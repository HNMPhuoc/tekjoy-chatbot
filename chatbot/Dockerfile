# ---- Base image nhẹ ----
FROM python:3.11-slim AS base

WORKDIR /app

# ---- Cài dependency hệ thống cần thiết ----
# Giảm tối đa gói, chỉ giữ những gói thật sự cần cho OCR + PDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    ffmpeg \
    libsm6 \
    libxext6 \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# ---- Bật cache pip để build lại nhanh ----
# Sử dụng BuildKit cache của Docker (yêu cầu Docker 24+)
# ⚠️ Cực kỳ hiệu quả khi build nhiều lần
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# ---- Copy và cài requirements ----
COPY requirements.txt .

# ---- Cài pip dependencies nhanh nhất có thể ----
# 1️⃣ Dùng binary wheels nếu có
# 2️⃣ Cache pip để không phải download lại
# 3️⃣ Cài torch riêng để tránh build source
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install --prefer-binary torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --prefer-binary -r requirements.txt

# ---- Copy project code ----
COPY app/ app/
COPY temp/ temp/
COPY uploads/ uploads/
COPY .env .

EXPOSE 8001

# ---- Command ----
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--workers", "4", "--bind", "0.0.0.0:8001"]
