@echo off
REM Chuyển đến thư mục chứa mã nguồn
cd /d D:\Tekjoy\chatbot

REM Kích hoạt môi trường ảo (nếu có)
call venv\Scripts\activate

REM Chạy Uvicorn trên port 3000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
pause
