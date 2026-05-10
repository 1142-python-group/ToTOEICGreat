from fastapi import APIRouter, Depends, HTTPException, Query
from routers.account_service.authen import verify_token
from supabase import create_client, Client
import os
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/leaderboard", tags=["Leaderboard"])

# 初始化 Supabase Client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SECRET_KEY")
if not url or not key:
    raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SECRET_KEY 環境變數")

supabase: Client = create_client(url, key)

class LeaderboardScoreEntry(BaseModel):
    rank: int
    user_id: str
    username: Optional[str]
    score: int
    is_me: bool

class LeaderboardDiligenceEntry(BaseModel):
    rank: int
    user_id: str
    username: Optional[str]
    total_questions_solved: int
    is_me: bool

@router.get("/scores", response_model=List[LeaderboardScoreEntry])
async def get_score_leaderboard(
    timeframe: str = Query("all_time", regex="^(all_time|this_month)$"),
    user_id: str = Depends(verify_token)
):
    """
    獲取最高分排行榜 (模考)
    """
    try:
        # 呼叫 RPC 函數
        res = supabase.rpc("get_score_leaderboard", {
            "target_user_id": user_id,
            "timeframe": timeframe
        }).execute()
        
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取排行榜失敗: {str(e)}")

@router.get("/diligence", response_model=List[LeaderboardDiligenceEntry])
async def get_diligence_leaderboard(
    timeframe: str = Query("this_week", regex="^(this_week|this_month|all_time)$"),
    user_id: str = Depends(verify_token)
):
    """
    獲取勤勉排行榜 (刷題數)
    """
    try:
        # 呼叫 RPC 函數
        res = supabase.rpc("get_diligence_leaderboard", {
            "target_user_id": user_id,
            "timeframe": timeframe
        }).execute()
        
        return res.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取排行榜失敗: {str(e)}")
