@echo off
REM Chuyển đến thư mục chứa mã nguồn
cd /d D:\Tekjoy\Tekjoy-ChatBot-UI

REM Kích hoạt môi trường ảo (nếu có)
call venv\Scripts\activate

REM Chạy Uvicorn trên port 3000
python -m uvicorn main:app --host 127.0.0.1 --port 3000 --reload

pause
