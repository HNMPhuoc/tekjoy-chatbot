chạy - test : python app/test_db.py
chạy rieal: uvicorn app.main:app --reload --host 0.0.0.0 --port 8001


Tắt máy ảo venv & xóa venv
  - Tắt: deactivate
  - Xóa:
        *Kiểm tra tiến trình còn chạy không? tasklist | findstr python
        *Hủy tiến trình: taskkill /F /IM python.exe 
        *Xóa máy ảo: Remove-Item -Recurse -Force .\venv   
