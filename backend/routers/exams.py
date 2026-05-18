from fastapi import APIRouter, Depends, HTTPException
from routers.auth import verify_token
from database import supabase
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

router = APIRouter(prefix="/api/v1/exams", tags=["Exams"])

class UpdateErrorStatusRequest(BaseModel):
    review_status: str

@router.get("/history")
async def get_exam_history(attempt_type: Optional[str] = None, limit: int = 10, user_id: str = Depends(verify_token)):
    query = supabase.table("exam_attempts").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit)
    if attempt_type:
        query = query.eq("attempt_type", attempt_type)
        
    res = query.execute()
    return res.data

@router.get("/errors")
async def get_error_book(status: str = "needs_review", part: Optional[int] = None, user_id: str = Depends(verify_token)):
    # 執行 JOIN 查詢
    query = supabase.table("answer_records").select(
        "*, questions!inner(question_id, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation, skill_tag, part, audio_path, translation, vocabulary, group_id)"
    ).eq("user_id", user_id).eq("is_correct", False).eq("review_status", status)
    
    if part:
        query = query.eq("questions.part", part)
        
    res = query.execute()
    data = res.data or []
    
    # 獲取所有 group_id 並抓取對應文章
    group_ids = list({r["questions"]["group_id"] for r in data if r["questions"].get("group_id")})
    articles_map = {}
    if group_ids:
        art_res = supabase.table("article").select("*").in_("group_id", group_ids).execute()
        for art in art_res.data:
            articles_map[art["group_id"]] = art
            
    # 將文章資訊塞回資料中
    for r in data:
        gid = r["questions"].get("group_id")
        if gid and gid in articles_map:
            r["questions"]["article"] = articles_map[gid]
        else:
            r["questions"]["article"] = None
            
    return data

@router.get("/history/{attempt_id}/answers")
async def get_exam_answers(attempt_id: str, user_id: str = Depends(verify_token)):
    query = supabase.table("answer_records").select(
        "*, questions!inner(question_id, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation, skill_tag, part, audio_path, translation, vocabulary, group_id)"
    ).eq("user_id", user_id).eq("attempt_id", attempt_id)
    
    res = query.execute()
    data = res.data or []
    
    # 獲取所有 group_id 並抓取對應文章
    group_ids = list({r["questions"]["group_id"] for r in data if r["questions"].get("group_id")})
    articles_map = {}
    if group_ids:
        art_res = supabase.table("article").select("*").in_("group_id", group_ids).execute()
        for art in art_res.data:
            articles_map[art["group_id"]] = art
            
    # 將文章資訊塞回資料中
    for r in data:
        gid = r["questions"].get("group_id")
        if gid and gid in articles_map:
            r["questions"]["article"] = articles_map[gid]
        else:
            r["questions"]["article"] = None
            
    return data

@router.patch("/errors/{record_id}")
async def update_error_status(record_id: str, request: UpdateErrorStatusRequest, user_id: str = Depends(verify_token)):
    res = supabase.table("answer_records").update({
        "review_status": request.review_status
    }).eq("id", record_id).eq("user_id", user_id).execute()
    
    if not res.data:
        raise HTTPException(status_code=404, detail="找不到該筆紀錄或無權限修改")
        
    return {"status": "updated", "record": res.data[0]}
