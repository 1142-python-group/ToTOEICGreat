"""
多多益善 — FastAPI 後端主程式
配合 Supabase 資料庫欄位名稱：
  question_id, question_text, option_a~d,
  skill_tag, correct_answer(a/b/c/d),
  explanation, translation, vocabulary
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import random
import uuid
from database import supabase
from models import Question, QuizSession, AnswerSubmit, QuestionResult, ExamResult, UserStats

from routers.account_service.authen import app as auth_app
from routers.friendship_service.friends import router as friendship_router
from routers.record_services.records import router as record_router
from routers.leaderboard_service.leaderboard import router as leaderboard_router


app = FastAPI(title="多多益善 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ════════════════════════════════════════════════
# 輔助函式：把字母答案轉成 index
# ════════════════════════════════════════════════

def letter_to_index(letter: str) -> int:
    """
    Supabase 的 correct_answer 欄位是 'A'/'B'/'C'/'D'
    轉成前端需要的 0/1/2/3
    """
    mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
    result = mapping.get(str(letter).strip().upper())
    if result is None:
        raise ValueError(f"無效的答案欄位值：'{letter}'，應為 A/B/C/D")
    return result


# ════════════════════════════════════════════════
# 讀取題庫從 Supabase
# ════════════════════════════════════════════════

try:
    # 從 Supabase 讀取所有題目
    res = supabase.table("questions").select("*").execute()
    questions_data = res.data
    print(f"✅ 題庫載入成功：共 {len(questions_data)} 道題目")

except Exception as e:
    print(f"⚠️  題庫載入失敗：{e}")
    questions_data = []


# ════════════════════════════════════════════════
# Session 暫存
# ════════════════════════════════════════════════

exam_sessions: dict = {}


# ════════════════════════════════════════════════
# API 端點
# ════════════════════════════════════════════════

# 整合原本在 authen.py 中的路由 (例如 /me)
app.include_router(auth_app.router)

# 註冊好友系統路由
app.include_router(friendship_router)

# 註冊測驗與紀錄系統路由
app.include_router(record_router)

# 註冊排行榜系統路由
app.include_router(leaderboard_router)

@app.get("/")
def root():
    return {
        "message": "多多益善 API 正常運作！",
        "total_questions": len(questions_data),
    }


@app.get("/api/quiz/start", response_model=QuizSession)
def start_quiz(count: int = 5):
    """從 Supabase 題庫隨機抽題，回傳題目（不含正確答案）。"""
    if not questions_data:
        raise HTTPException(503, detail="題庫未載入，請確認 Supabase 是否正常連線")
    if len(questions_data) < count:
        raise HTTPException(400, detail=f"題庫只有 {len(questions_data)} 題，無法抽出 {count} 題")

    sampled = random.sample(questions_data, count)
    session_id = str(uuid.uuid4())

    questions = []
    correct_answers = {}

    for row in sampled:
        qid = str(row["question_id"])

        try:
            correct_idx = letter_to_index(row["correct_answer"])
        except ValueError as e:
            raise HTTPException(500, detail=f"題目 {qid} 的答案欄位有誤：{e}")

        questions.append(Question(
            id=qid,
            tag=str(row.get("skill_tag", "未分類")),
            text=str(row["question_text"]),
            options=[
                str(row.get("option_a", "")),
                str(row.get("option_b", "")),
                str(row.get("option_c", "")),
                str(row.get("option_d", "")),
            ],
        ))
        correct_answers[qid] = correct_idx

    exam_sessions[session_id] = {
        "questions":       sampled,
        "correct_answers": correct_answers,
    }

    return QuizSession(
        session_id=session_id,
        questions=questions,
        time_limit_seconds=900,
    )


@app.post("/api/quiz/submit", response_model=ExamResult)
def submit_quiz(payload: AnswerSubmit):
    """
    交卷：對答案，解析直接讀題庫欄位的 explanation。
    """
    session = exam_sessions.get(payload.session_id)
    if not session:
        raise HTTPException(404, detail="找不到此考試 session，可能已過期")

    correct_answers: dict = session["correct_answers"]
    questions_data: list  = session["questions"]

    correct_count    = 0
    wrong_count      = 0
    unanswered_count = 0
    question_results = []
    total_time       = sum(payload.time_spent_per_q.values())

    for row in questions_data:
        qid         = str(row["question_id"])
        correct_idx = correct_answers[qid]
        user_ans    = payload.answers.get(qid)
        is_correct  = (user_ans == correct_idx)

        if user_ans is None:
            unanswered_count += 1
        elif is_correct:
            correct_count += 1
        else:
            wrong_count += 1

        ai_analysis = str(row.get("explanation", "解析尚未提供"))
        translation = str(row.get("translation", ""))

        raw_vocab  = str(row.get("vocabulary", ""))
        vocab_list = [v.strip() for v in raw_vocab.replace("、", ",").split(",") if v.strip()]

        question_results.append(QuestionResult(
            question_id=qid,
            tag=str(row.get("skill_tag", "未分類")),
            question_text=str(row["question_text"]),
            options=[
                str(row.get("option_a", "")),
                str(row.get("option_b", "")),
                str(row.get("option_c", "")),
                str(row.get("option_d", "")),
            ],
            correct_index=correct_idx,
            user_answer=user_ans,
            is_correct=is_correct,
            ai_analysis=ai_analysis,
            translation=translation,
            vocab=vocab_list,
        ))

    total_q = len(questions_data)
    score   = round((correct_count / total_q) * 100) if total_q else 0

    del exam_sessions[payload.session_id]

    return ExamResult(
        score=score,
        correct_count=correct_count,
        wrong_count=wrong_count,
        unanswered_count=unanswered_count,
        total_time_seconds=total_time,
        question_results=question_results,
    )


@app.get("/api/user/{user_id}/stats", response_model=UserStats)
def get_user_stats(user_id: str):
    """暫時回傳假資料，正式版改從資料庫查詢。"""
    return UserStats(
        username="測試考生",
        total_questions=143,
        estimated_score=750,
        avg_time_per_q=42.0,
        score_history=[
            {"month": "1月", "score": 580},
            {"month": "2月", "score": 615},
            {"month": "3月", "score": 640},
            {"month": "4月", "score": 670},
            {"month": "5月", "score": 715},
            {"month": "6月", "score": 750},
        ],
        radar_data=[
            {"label": "文法",     "value": 75},
            {"label": "單字",     "value": 82},
            {"label": "閱讀理解", "value": 68},
            {"label": "推論能力", "value": 72},
            {"label": "商業用語", "value": 88},
            {"label": "聽力",    "value": 60},
        ],
    )


@app.post("/api/quiz/generate-practice")
def generate_practice(question_id: str):
    """從題庫找相同 skill_tag 的其他題目當練習題。"""
    if not questions_data:
        raise HTTPException(503, detail="題庫未載入")

    original = [q for q in questions_data if str(q.get("question_id")) == question_id]
    if not original:
        raise HTTPException(404, detail=f"找不到題目 {question_id}")

    tag = original[0].get("skill_tag")
    same_tag = [q for q in questions_data if q.get("skill_tag") == tag and str(q.get("question_id")) != question_id]

    if not same_tag:
        raise HTTPException(404, detail="找不到相同考點的其他題目")

    row = random.choice(same_tag)
    return {
        "id":      str(row.get("question_id", "")),
        "tag":     str(row.get("skill_tag", "")),
        "text":    str(row.get("question_text", "")),
        "options": [
            str(row.get("option_a", "")),
            str(row.get("option_b", "")),
            str(row.get("option_c", "")),
            str(row.get("option_d", "")),
        ],
    }