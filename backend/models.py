from pydantic import BaseModel
from typing import Optional

# ── 題目相關 ──────────────────────────────────
class Question(BaseModel):
    id: str
    tag: str                    # 例如：「單字 — 動詞」
    text: str                   # 題目文字
    options: list[str]          # ["A. ...", "B. ...", "C. ...", "D. ..."]
    # Part 7 閱讀題欄位
    article_text: Optional[str] = None
    article_type: Optional[str] = None
    article_translation: Optional[str] = None   # 新增
    group_id: Optional[str] = None              # 新增，前端用來判斷同組題目
    audio_url: Optional[str] = None                # 聽力題的音檔 URL
    part: Optional[int] = None              # 2/3/4/5/7，前端用來顯示不同圖示
    # 注意：correct 欄位不回傳給前端！交卷後才由後端判斷

class QuizSession(BaseModel):
    session_id: str             # 這次考試的唯一 ID
    questions: list[Question]   # 5 道題目
    time_limit_seconds: int     # 限時秒數，例如 900

# ── 交卷相關 ──────────────────────────────────
class AnswerSubmit(BaseModel):
    session_id: str
    answers: dict[str, int]          # { 題目id: 選項index(0-3) }
    time_spent_per_q: dict[str, int] # { 題目id: 花費秒數 }
    attempt_type: Optional[str] = "practice"  # 新增：區分練習或模考

# ── 成績 / 解析 ───────────────────────────────
class QuestionResult(BaseModel):
    question_id: str
    tag: str
    question_text: str
    options: list[str]
    correct_index: int          # 正確答案的 index
    user_answer: Optional[int]  # 使用者的答案（None = 未作答）
    is_correct: bool
    ai_analysis: str            # LLM 生成的解析
    translation: str            # 中文翻譯
    vocab: list[str]            # 關鍵單字
    # Part 7 閱讀題欄位（結果頁顯示文章用）
    article_text: Optional[str] = None
    article_type: Optional[str] = None
    article_translation: Optional[str] = None
    group_id: Optional[str] = None
    audio_url: Optional[str] = None  # 聽力題的音檔 URL
    part: Optional[int] = None              # 2/3/4/5/7，前端用來顯示不同圖示

class ExamResult(BaseModel):
    score: int                  # 0-100
    correct_count: int
    wrong_count: int
    unanswered_count: int
    total_time_seconds: int
    question_results: list[QuestionResult]

# ── 使用者 / 儀表板 ───────────────────────────
class UserStats(BaseModel):
    username: str
    total_questions: int
    estimated_score: int
    avg_time_per_q: float
    score_history: list[dict]   # [{"month": "1月", "score": 580}, ...]
    radar_data: list[dict]      # [{"label": "文法", "value": 75}, ...]