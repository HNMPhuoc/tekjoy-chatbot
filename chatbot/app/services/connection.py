import os
import psycopg

# Thư viện dotenv được sử dụng để tải các biến môi trường từ file .env.
# Tốt nhất nên cài đặt: pip install python-dotenv
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env.
load_dotenv()

def get_db_connection():
    """
    Hàm này tạo và trả về một đối tượng kết nối đến cơ sở dữ liệu PostgreSQL.
    Các thông tin kết nối được lấy từ các biến môi trường.
    """
    try:
        conn = psycopg.connect(
            dbname=os.getenv("PG_DATABASE"),
            user=os.getenv("PG_USER"),
            password=os.getenv("PG_PASSWORD"),
            host=os.getenv("PG_HOST"),
            port=os.getenv("PG_PORT")
        )
        print("Kết nối đến cơ sở dữ liệu PostgreSQL thành công!")
        return conn
    except Exception as e:
        print(f"Lỗi khi kết nối đến cơ sở dữ liệu: {e}")
        return None

# Đoạn mã dưới đây dùng để kiểm tra kết nối.
# Nó sẽ chạy khi bạn thực thi file này trực tiếp.
if __name__ == "__main__":
    conn = get_db_connection()
    if conn:
        try:
            # Tạo một cursor để thực thi các lệnh SQL
            with conn.cursor() as cur:
                # Thực thi một truy vấn đơn giản để lấy phiên bản của PostgreSQL
                cur.execute("SELECT version();")
                db_version = cur.fetchone()
                print(f"Phiên bản PostgreSQL của bạn là: {db_version[0]}")
        finally:
            # Đảm bảo kết nối được đóng sau khi sử dụng
            conn.close()
            print("Kết nối đã được đóng.")