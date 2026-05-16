## 前端啟動指令
cd frontend
python -m http.server 3000

## 後端啟動指令
cd backend
uvicorn main:app --reload --port 8000