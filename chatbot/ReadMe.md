# Tekjoy Backend

Dự án này là một server backend được xây dựng trên nền tảng **Python**, sử dụng **PostgresDB** làm cơ sở dữ liệu. Nó được thiết kế để cung cấp các API mạnh mẽ và có khả năng mở rộng cho ứng dụng của bạn.

---

## Clone repository
1.  Clone repository về máy tính của bạn:
    ```bash
    git clone https://github.com/HNMPhuoc/tekjoy-chatbot.git
    ```
---

2.  Cài đặt môi trường

    Sử dụng terminal tạo máy ảo
    ```bash
    python -m venv venv
    ```
    Kích hoạt máy ảo venv
    ```bash
    .\venv\Scripts\activate
    ```

3. Tải thư viện vào máy ảo
    ```bash
    pip install -r requirements.txt
    ```
    
4. Chạy server
Sử dụng lệnh uvicorn 1:
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ```
    Hoặc dùng lệnh uvicorn 2:
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8000
    ```
5. Tạo file env

   ```bash
        # ==============================================================================
    # File: .env.example
    #
    # Hướng dẫn:
    # 1. Tạo một bản sao và đổi tên thành `.env`.
    # 2. Thay thế các giá trị bên dưới bằng thông tin thực tế của bạn.
    # ==============================================================================
    
    DATABASE_URL="postgresql+asyncpg://postgres:123456@localhost:5432/TekjoyV4"
    OPENAI_API_KEY="your_open_api_key"
    PADDLE_OCR_API_URL = http://thien-ocr:8080/ocr-fullV2
    
    PG_HOST=db
    PG_PORT=5432
    PG_DATABASE=Tekjoy
    PG_USER=admin
    PG_PASSWORD=admin123
    
    
    SECRET_KEY=your_secret_key
    ALGORITHM = "HS256"
    ```
