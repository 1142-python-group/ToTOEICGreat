from fastapi import APIRouter, HTTPException
from ..models import AnswerSubmit, ExamResult, QuestionResult
from ..database import supabase
from ..main import letter_to_index, questions_data
from ..routers.quiz import quiz_sessions
from typing import Dict
import uuid

router = APIRouter(prefix="/api/v1/result", tags=["Result"])

@router.post("/submit", response_model=ExamResult)
async def submit_answers(submit: AnswerSubmit):
    """
    提交答案並計算成績
    """
    if submit.session_id not in quiz_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = quiz_sessions[submit.session_id]
    questions = session_data["questions"]

    # 建立題目 ID 到資料的映射
    question_map = {q["question_id"]: q for q in questions_data}

    question_results = []
    correct_count = 0
    total_time = sum(submit.time_spent_per_q.values())

    for q in questions:
        q_data = question_map.get(q["id"])
        if not q_data:
            continue

        user_answer = submit.answers.get(q["id"])
        correct_index = letter_to_index(q_data["correct_answer"])
        is_correct = (user_answer == correct_index) if user_answer is not None else False

        if is_correct:
            correct_count += 1

        result = QuestionResult(
            question_id=q["id"],
            tag=q_data.get("skill_tag", "未分類"),
            question_text=q_data["question_text"],
            options=[
                q_data["option_a"],
                q_data["option_b"],
                q_data.get("option_c", ""),
                q_data.get("option_d", "")
            ],
            correct_index=correct_index,
            user_answer=user_answer,
            is_correct=is_correct,
            ai_analysis=q_data.get("explanation", "無解析"),
            translation=q_data.get("translation", "無翻譯"),
            vocab=q_data.get("vocabulary", "").split(",") if q_data.get("vocabulary") else []
        )
        question_results.append(result)

    # 計算分數（簡單算法：每題 20 分）
    score = correct_count * 20

    exam_result = ExamResult(
        score=score,
        correct_count=correct_count,
        wrong_count=len(question_results) - correct_count,
        unanswered_count=sum(1 for r in question_results if r.user_answer is None),
        total_time_seconds=total_time,
        question_results=question_results
    )

    # 清理 session
    del quiz_sessions[submit.session_id]

    return exam_result