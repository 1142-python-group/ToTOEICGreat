"""
多多益善 — FastAPI 後端主程式
配合實際 CSV 欄位名稱：
  question_id, question_text, option_a~d,
  skill_tag, correct_answer(a/b/c/d),
  explanation, translation, vocabulary
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import uuid

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
    CSV 的 correct_answer 欄位是 'a'/'b'/'c'/'d'（大小寫都接受）
    轉成前端需要的 0/1/2/3
    """
    mapping = {"a": 0, "b": 1, "c": 2, "d": 3}
    result = mapping.get(str(letter).strip().lower())
    if result is None:
        raise ValueError(f"無效的答案欄位值：'{letter}'，應為 a/b/c/d")
    return result


# ════════════════════════════════════════════════
# 讀取 CSV
# ════════════════════════════════════════════════

try:
    df = pd.read_csv("questions.csv", encoding="utf-8")

    required_cols = [
        "question_id", "question_text",
        "option_a", "option_b", "option_c", "option_d",
        "skill_tag", "correct_answer",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSV 缺少欄位：{missing}")

    print(f"✅ 題庫載入成功：共 {len(df)} 道題目")

except FileNotFoundError:
    print("⚠️  找不到 questions.csv，請放在 backend/ 資料夾下")
    df = pd.DataFrame()
except ValueError as e:
    print(f"⚠️  CSV 格式錯誤：{e}")
    df = pd.DataFrame()


# ════════════════════════════════════════════════
# Pydantic 模型
# ════════════════════════════════════════════════

class Question(BaseModel):
    id: str
    tag: str
    text: str
    options: list[str]

class QuizSession(BaseModel):
    session_id: str
    questions: list[Question]
    time_limit_seconds: int

class AnswerSubmit(BaseModel):
    session_id: str
    answers: dict[str, int]          # { "R001": 2, "R002": 0, ... }
    time_spent_per_q: dict[str, int] # { "R001": 45, ... }

class QuestionResult(BaseModel):
    question_id: str
    tag: str
    question_text: str
    options: list[str]
    correct_index: int
    user_answer: Optional[int]
    is_correct: bool
    ai_analysis: str
    translation: str
    vocab: list[str]

class ExamResult(BaseModel):
    score: int
    correct_count: int
    wrong_count: int
    unanswered_count: int
    total_time_seconds: int
    question_results: list[QuestionResult]

class UserStats(BaseModel):
    username: str
    total_questions: int
    estimated_score: int
    avg_time_per_q: float
    score_history: list[dict]
    radar_data: list[dict]


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
        "total_questions": len(df),
    }


@app.get("/api/quiz/start", response_model=QuizSession)
def start_quiz(count: int = 5):
    """從 CSV 隨機抽題，回傳題目（不含正確答案）。"""
    if df.empty:
        raise HTTPException(503, detail="題庫未載入，請確認 questions.csv 存在且格式正確")
    if len(df) < count:
        raise HTTPException(400, detail=f"題庫只有 {len(df)} 題，無法抽出 {count} 題")

    sampled = df.sample(n=count).to_dict("records")
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
            tag=str(row["skill_tag"]),
            text=str(row["question_text"]),
            options=[
                str(row["option_a"]),
                str(row["option_b"]),
                str(row["option_c"]),
                str(row["option_d"]),
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
    交卷：對答案，解析直接讀 CSV 的 explanation 欄位，不呼叫 LLM。
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

        # 解析直接從 CSV 讀，不需要任何 LLM 呼叫
        ai_analysis = str(row.get("explanation", "解析尚未提供"))
        translation = str(row.get("translation", ""))

        # vocabulary 欄位支援頓號或逗號分隔
        raw_vocab  = str(row.get("vocabulary", ""))
        vocab_list = [v.strip() for v in raw_vocab.replace("、", ",").split(",") if v.strip()]

        question_results.append(QuestionResult(
            question_id=qid,
            tag=str(row["skill_tag"]),
            question_text=str(row["question_text"]),
            options=[
                str(row["option_a"]),
                str(row["option_b"]),
                str(row["option_c"]),
                str(row["option_d"]),
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
    if df.empty:
        raise HTTPException(503, detail="題庫未載入")

    original = df[df["question_id"] == question_id]
    if original.empty:
        raise HTTPException(404, detail=f"找不到題目 {question_id}")

    tag      = original.iloc[0]["skill_tag"]
    same_tag = df[(df["skill_tag"] == tag) & (df["question_id"] != question_id)]

    if same_tag.empty:
        raise HTTPException(404, detail="找不到相同考點的其他題目")

    row = same_tag.sample(n=1).iloc[0]
    return {
        "id":      str(row["question_id"]),
        "tag":     str(row["skill_tag"]),
        "text":    str(row["question_text"]),
        "options": [
            str(row["option_a"]),
            str(row["option_b"]),
            str(row["option_c"]),
            str(row["option_d"]),
        ],
    }