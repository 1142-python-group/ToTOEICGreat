from fastapi import FastAPI
from account_service.authen import app as auth_app
from friendship_service.friends import router as friendship_router
from record_services.records import router as record_router
from leaderboard_service.leaderboard import router as leaderboard_router
import uvicorn

app = FastAPI(title="ToToeicGreat API Server")

# 整合原本在 authen.py 中的路由 (例如 /me)
app.include_router(auth_app.router)

# 註冊好友系統路由
app.include_router(friendship_router)

# 註冊測驗與紀錄系統路由
app.include_router(record_router)

# 註冊排行榜系統路由
app.include_router(leaderboard_router)

@app.get("/")
async def root():
    return {"message": "Welcome to ToToeicGreat API Server"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
