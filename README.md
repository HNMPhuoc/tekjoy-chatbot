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
    uvicorn main:app --host 0.0.0.0 --port 8001 --reload
    ```
    Hoặc dùng lệnh uvicorn 2:
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8001
    ```
5. Tạo file env

   ```bash
    DATABASE_URL="postgresql://postgres:user1@localhost:5432/db_pione"
    # Database URL format: postgresql://<user>:<password>@<host>:<port>/<dbname>
    # DATABASE_URL="postgresql://postgres:your_strong_password@localhost:5432/your_db_name"
    
    # JWT Settings
    SECRET_KEY="your-secret-key"
    ALGORITHM="HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES=60
    ```
