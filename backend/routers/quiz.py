from fastapi import APIRouter, HTTPException
from ..models import Question, QuizSession
from ..database import supabase
import random
import uuid
from ..main import letter_to_index, questions_data

router = APIRouter(prefix="/api/v1/quiz", tags=["Quiz"])

# 暫存 session 資料（實際應存到資料庫或 Redis）
quiz_sessions: dict = {}

@router.post("/start", response_model=QuizSession)
async def start_quiz():
    """
    開始測驗：隨機抽取 5 道題目
    """
    if not questions_data:
        raise HTTPException(status_code=500, detail="題庫載入失敗")

    # 隨機抽取 5 道題目
    selected_questions = random.sample(questions_data, min(5, len(questions_data)))

    questions = []
    for q in selected_questions:
        try:
            correct_index = letter_to_index(q["correct_answer"])
            question = Question(
                id=q["question_id"],
                tag=q.get("skill_tag", "未分類"),
                text=q["question_text"],
                options=[
                    q["option_a"],
                    q["option_b"],
                    q.get("option_c", ""),
                    q.get("option_d", "")
                ]
            )
            questions.append(question)
        except Exception as e:
            print(f"題目 {q['question_id']} 處理錯誤: {e}")
            continue

    if not questions:
        raise HTTPException(status_code=500, detail="無法生成題目")

    session = QuizSession(
        session_id=str(uuid.uuid4()),
        questions=questions,
        time_limit_seconds=900  # 15 分鐘
    )

    # 儲存 session 資料
    quiz_sessions[session.session_id] = {
        "questions": selected_questions
    }

    return session