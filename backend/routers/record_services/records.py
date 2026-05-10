from fastapi import APIRouter, Depends, HTTPException
from routers.account_service.authen import verify_token
from supabase import create_client, Client
import os
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

router = APIRouter(prefix="/api/v1/exams", tags=["Exams"])

# 初始化 Supabase Client
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SECRET_KEY")
if not url or not key:
    raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SECRET_KEY 環境變數")

supabase: Client = create_client(url, key)

class AnswerItem(BaseModel):
    question_id: str
    user_answer: Optional[str]
    time_spent: int

class SubmitExamRequest(BaseModel):
    attempt_type: str
    config: Optional[Dict] = None
    total_time_spent: int
    answers: List[AnswerItem]

class UpdateErrorStatusRequest(BaseModel):
    review_status: str

@router.post("/submit")
async def submit_exam(request: SubmitExamRequest, user_id: str = Depends(verify_token)):
    # 1. 獲取題目正確答案進行比對
    question_ids = [a.question_id for a in request.answers]
    questions_res = supabase.table("questions").select("question_id, correct_answer").in_("question_id", question_ids).execute()
    
    correct_map = {q["question_id"]: q["correct_answer"] for q in questions_res.data}
    
    # 2. 統計計算
    total_questions = len(request.answers)
    correct_answers = 0
    records_to_insert = []
    
    for ans in request.answers:
        is_correct = ans.user_answer == correct_map.get(ans.question_id)
        if is_correct:
            correct_answers += 1
        
        records_to_insert.append({
            "user_id": user_id,
            "question_id": ans.question_id,
            "user_answer": ans.user_answer,
            "is_correct": is_correct,
            "time_spent": ans.time_spent,
            "review_status": "needs_review" if not is_correct else None
        })
    
    accuracy_rate = correct_answers / total_questions if total_questions > 0 else 0
    
    # 3. 寫入測驗紀錄 (exam_attempts)
    attempt_data = {
        "user_id": user_id,
        "attempt_type": request.attempt_type,
        "config": request.config,
        "total_questions": total_questions,
        "correct_answers": correct_answers,
        "accuracy_rate": accuracy_rate,
        "total_time_spent": request.total_time_spent,
    }
    
    # 這裡實務上建議用 RPC 以確保原子性，或先 insert header 再 insert details
    attempt_res = supabase.table("exam_attempts").insert(attempt_data).execute()
    if not attempt_res.data:
        raise HTTPException(status_code=500, detail="無法建立測驗紀錄")
    
    attempt_id = attempt_res.data[0]["id"]
    
    # 4. 批次寫入作答明細 (answer_records)
    for r in records_to_insert:
        r["attempt_id"] = attempt_id
        
    records_res = supabase.table("answer_records").insert(records_to_insert).execute()
    
    return {
        "attempt_id": attempt_id,
        "correct_answers": correct_answers,
        "total_questions": total_questions,
        "accuracy_rate": accuracy_rate
    }

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
        "*, questions!inner(question_text, option_a, option_b, option_c, option_d, correct_answer, explanation, skill_tag, part)"
    ).eq("user_id", user_id).eq("is_correct", False).eq("review_status", status)
    
    if part:
        query = query.eq("questions.part", part)
        
    res = query.execute()
    return res.data

@router.get("/history/{attempt_id}/answers")
async def get_exam_answers(attempt_id: str, user_id: str = Depends(verify_token)):
    query = supabase.table("answer_records").select(
        "*, questions!inner(question_text, option_a, option_b, option_c, option_d, correct_answer, explanation, skill_tag, part)"
    ).eq("user_id", user_id).eq("attempt_id", attempt_id)
    
    res = query.execute()
    return res.data

@router.patch("/errors/{record_id}")
async def update_error_status(record_id: str, request: UpdateErrorStatusRequest, user_id: str = Depends(verify_token)):
    res = supabase.table("answer_records").update({
        "review_status": request.review_status
    }).eq("id", record_id).eq("user_id", user_id).execute()
    
    if not res.data:
        raise HTTPException(status_code=404, detail="找不到該筆紀錄或無權限修改")
        
    return {"status": "updated", "record": res.data[0]}
