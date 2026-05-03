from fastapi import FastAPI
from account_service.authen import app as auth_app
from friendship_service.friends import router as friendship_router
import uvicorn

app = FastAPI(title="ToToeicGreat API Server")

# 整合原本在 authen.py 中的路由 (例如 /me)
app.include_router(auth_app.router)

# 註冊好友系統路由
app.include_router(friendship_router)

@app.get("/")
async def root():
    return {"message": "Welcome to ToToeicGreat API Server"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
