from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from account_service.authen import verify_token
import os
from supabase import create_client, Client

# 初始化 Supabase Client
url: str = os.environ.get("SUPABASE_URL")
# 後端 Service 務必使用 SUPABASE_SECRET_KEY 以繞過 RLS 的 auth.uid() 限制
key: str = os.environ.get("SUPABASE_SECRET_KEY")

if not url or not key:
    raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SECRET_KEY 環境變數")

supabase: Client = create_client(url, key)


router = APIRouter(prefix="/api/v1/friends", tags=["Friendship"])

# --- Pydantic Models ---

class FriendRequestCreate(BaseModel):
    target_user_id: UUID

class FriendRequestAction(BaseModel):
    action: str = Field(..., pattern="^(accept|reject)$")

class FriendshipResponse(BaseModel):
    friendship_id: UUID
    friend_user_id: UUID
    friend_username: Optional[str]
    status: str
    created_at: datetime

class FriendListResponse(BaseModel):
    data: List[FriendshipResponse]

# --- API Endpoints ---

@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def send_friend_request(
    request: FriendRequestCreate, 
    user_id: str = Depends(verify_token)
):
    """發送好友邀請"""
    try:
        # 強制轉為字串避免 UUID 物件在 SDK 中產生不可預期的行為
        res = supabase.table("friendships").insert({
            "requester_id": str(user_id),
            "addressee_id": str(request.target_user_id),
            "status": "pending"
        }).execute()
        
        if not res.data:
            raise HTTPException(status_code=400, detail="邀請發送失敗")
            
        return {
            "message": "Friend request sent successfully", 
            "friendship_id": res.data[0]["id"]
        }
    except Exception as e:
        err_msg = str(e)
        if "unique_friendship_idx" in err_msg:
            raise HTTPException(status_code=409, detail="好友關係已存在或邀請已在等待中")
        # 捕捉 RLS 錯誤並提供更多訊息
        if "42501" in err_msg:
            raise HTTPException(status_code=403, detail=f"資料庫權限錯誤 (RLS): 請確認 Service Role Key 是否正確配置。")
        raise HTTPException(status_code=400, detail=err_msg)

@router.patch("/requests/{friendship_id}")
async def handle_friend_request(
    friendship_id: UUID,
    body: FriendRequestAction,
    user_id: str = Depends(verify_token)
):
    """接受或拒絕邀請"""
    if body.action == "accept":
        # 嚴格校驗：當前使用者必須是接收者
        res = supabase.table("friendships").update({"status": "accepted"})\
            .eq("id", str(friendship_id))\
            .eq("addressee_id", str(user_id))\
            .execute()
        
        if not res.data:
            raise HTTPException(status_code=403, detail="無權限處理此邀請或邀請不存在")
        return {"message": "Request accepted"}
    
    else: # reject
        res = supabase.table("friendships").delete()\
            .eq("id", str(friendship_id))\
            .eq("addressee_id", str(user_id))\
            .execute()
        
        if not res.data:
            raise HTTPException(status_code=403, detail="無權限處理此邀請或邀請不存在")
        return {"message": "Request rejected"}

@router.get("", response_model=FriendListResponse)
async def get_friends_list(
    status: str = "accepted",
    user_id: str = Depends(verify_token)
):
    """取得好友列表"""
    # 使用 .or_ 查詢包含自己的所有關係，並過濾狀態
    query = supabase.table("friendships").select(
        "id, status, created_at, requester_id, addressee_id, "
        "requester:requester_id(username), "
        "addressee:addressee_id(username)"
    ).or_(f"requester_id.eq.{user_id},addressee_id.eq.{user_id}")\
     .eq("status", status)
    
    res = query.execute()
    
    data = []
    for item in res.data:
        is_requester = str(item["requester_id"]) == str(user_id)
        friend_id = item["addressee_id"] if is_requester else item["requester_id"]
        # 安全取得 username
        friend_username = (item["addressee"]["username"] if is_requester else item["requester"]["username"]) if (item.get("addressee") or item.get("requester")) else "Unknown"
        
        data.append({
            "friendship_id": item["id"],
            "friend_user_id": friend_id,
            "friend_username": friend_username,
            "status": item["status"],
            "created_at": item["created_at"]
        })
        
    return {"data": data}

@router.delete("/{friend_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend_or_request(
    friend_user_id: UUID,
    user_id: str = Depends(verify_token)
):
    """解除好友或收回邀請"""
    # 只要我是其中一方即可刪除
    res = supabase.table("friendships").delete()\
        .or_(f"and(requester_id.eq.{user_id},addressee_id.eq.{friend_user_id}),"
            f"and(requester_id.eq.{friend_user_id},addressee_id.eq.{user_id})")\
        .execute()
    
    if not res.data:
        raise HTTPException(status_code=404, detail="好友關係不存在")
    return None
