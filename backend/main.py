"""
多多益善 — FastAPI 後端主程式
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import random
import uuid
import json
from database import supabase, SUPABASE_URL
from models import Question, QuizSession, AnswerSubmit, QuestionResult, ExamResult, UserStats
from pydantic import BaseModel
from collections import defaultdict

from routers.auth import router as auth_router, verify_token
from routers.friends import router as friendship_router
from routers.exams import router as record_router
from routers.leaderboard import router as leaderboard_router
from routers.history_practice import router as history_router


app = FastAPI(title="多多益善 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PracticeRequest(BaseModel):
    question_id: str

# ════════════════════════════════════════════════
# 輔助函式
# ════════════════════════════════════════════════

def letter_to_index(letter: str) -> int:
    mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
    result = mapping.get(str(letter).strip().upper())
    if result is None:
        raise ValueError(f"無效的答案欄位值：'{letter}'，應為 A/B/C/D")
    return result

def index_to_letter(idx: int) -> str:
    if idx is None:
        return None
    mapping = {0: "A", 1: "B", 2: "C", 3: "D"}
    return mapping.get(idx)

def classify_skill_tag(tag_raw):
    if isinstance(tag_raw, list):
        tag = tag_raw[0] if tag_raw else ""
    elif isinstance(tag_raw, str):
        try:
            parsed = json.loads(tag_raw)
            tag = parsed[0] if isinstance(parsed, list) else tag_raw
        except:
            tag = tag_raw
    else:
        tag = str(tag_raw)

    if tag.startswith("文法"):
        return "文法"
    elif tag.startswith("單字"):
        return "單字"
    elif tag.startswith("閱讀") or "細節理解" in tag or "原因理解" in tag or "主旨" in tag or "推論" in tag or "對話主旨" in tag:
        return "閱讀理解"
    elif "WH問句" in tag or "Yes/No" in tag or "附加問句" in tag or "否定疑問句" in tag or "選擇疑問句" in tag or "間接疑問句" in tag or "陳述句回應" in tag:
        return "聽力"
    elif "建議" in tag or "請求" in tag or "說話者意圖" in tag or "說話目的" in tag or "下一步行動" in tag or "推論(Inference)" in tag:
        return "推論能力"
    else:
        return "商業用語"

# ════════════════════════════════════════════════
# 讀取題庫（分批讀取資料庫資料）
# ════════════════════════════════════════════════

def load_all_questions() -> list:
    all_rows = []
    batch = 1000
    offset = 0
    while True:
        res = (
            supabase.table("questions")
            .select("*")
            .range(offset, offset + batch - 1)
            .execute()
        )
        rows = res.data or []
        all_rows.extend(rows)
        if len(rows) < batch:
            break
        offset += batch
    return all_rows

try:
    _all_questions = load_all_questions()
    vocalvulary_data = [q for q in _all_questions if q.get("part")==5]
    reading_data = [q for q in _all_questions if q.get("part") in (6,7)]
    listening_data = [q for q in _all_questions if q.get("part") in (1,2,3,4)]
    questions_data = vocalvulary_data + reading_data
    print(f"✅ 題庫載入：單字 {len(vocalvulary_data)} 題 + 閱讀 {len(reading_data)} 題 + 聽力 {len(listening_data)} 題 = 共 {len(questions_data)} 題")
    print(f"🎧 聽力分布：" + str({p: sum(1 for q in listening_data if q.get('part')==p) for p in [1,2,3,4]}))
except Exception as e:
    print(f"⚠️  題庫載入失敗：{e}")
    vocalvulary_data = reading_data = listening_data = questions_data = []

exam_sessions: dict = {}

# ════════════════════════════════════════════════
# Router 掛載
# ════════════════════════════════════════════════

# 整合原本在 authen.py 中的路由 (例如 /me)
app.include_router(auth_router)

# 註冊好友系統路由
app.include_router(friendship_router)
app.include_router(record_router)
app.include_router(leaderboard_router)
app.include_router(history_router)

@app.get("/")
def root():
    return {
        "message": "多多益善 API 正常運作！",
        "total_questions": len(questions_data),
    }


# ════════════════════════════════════════════════
# 開始測驗
# ════════════════════════════════════════════════

@app.get("/api/quiz/start", response_model=QuizSession)
def start_quiz(
    vocab_count: int = 5,        # 單字題數
    listening_count: int = 3,    # 聽力題數
    reading_groups: int = 1,     # 閱讀組數（Part 6+7 合計）
    include_listening: bool = True,
    include_vocab: bool = True,
    include_reading: bool = True,
    ):
    """
    抽題策略：
      - 單字題（group_id 為 None）：固定抽 count 題，隨機打亂順序排在前面
      - 閱讀題（有 group_id）：額外抽 READING_GROUPS_PER_QUIZ 組，
        每組全部題目接在單字題後面（不佔 count 名額，不拆散同組）
      - 總題數 = count + 閱讀題數（通常 2~4 題）
      - 想要更多組閱讀：修改 READING_GROUPS_PER_QUIZ 即可
    """
    if not questions_data:
        raise HTTPException(503, detail="題庫未載入，請確認 Supabase 是否正常連線")

    # # 1. 分類
    # standalone = vocalvulary_data
    # reading_groups: dict[str, list] = {}
    # for q in reading_data:
    #     gid = q.get("group_id")
    #     if not gid:
    #         continue
    #     reading_groups.setdefault(gid, []).append(q)
    # 1. 分類（Part 6 + Part 7 都算閱讀題）
    standalone = vocalvulary_data
    reading_group_map: dict[str, list] = {}
    for q in reading_data:   # reading_data 要包含 part 6
        gid = q.get("group_id")
        if not gid:
            continue
        reading_group_map.setdefault(gid, []).append(q)

    # # 2. 抽單字題
    # if len(standalone) < vocab_count:
    #     raise HTTPException(400, detail=f"單字題不足，只有 {len(standalone)} 題")
    # standalone_sampled = random.sample(standalone, count)
    # random.shuffle(standalone_sampled)
    # # 3. 抽聽力題（不計入單字題數量）
    # LISTENING_COUNT = 3
    # listening_sampled: list = []
    # if listening_data and len(listening_data) >= LISTENING_COUNT:
    #     listening_sampled = random.sample(listening_data, LISTENING_COUNT)
    #     print(f"🎧 同時抽取了 {len(listening_sampled)} 題聽力題（不計入單字題數量）")
    # # 4. 抽閱讀題（整組，不拆散）
    # READING_GROUPS_PER_QUIZ = 1   # ← 想要幾組閱讀就改這裡
    # reading_sampled: list = []
    # if reading_groups:
    #     chosen_ids = random.sample(
    #         list(reading_groups.keys()),
    #         min(READING_GROUPS_PER_QUIZ, len(reading_groups))
    #     )
    #     for gid in chosen_ids:
    #         reading_sampled.extend(reading_groups[gid])

    # sampled = listening_sampled + standalone_sampled + reading_sampled
    # 2. 抽單字題
    standalone_sampled: list = []
    if include_vocab:
        if len(standalone) < vocab_count:
            raise HTTPException(400, detail=f"單字題不足，只有 {len(standalone)} 題")
        standalone_sampled = random.sample(standalone, vocab_count)
        random.shuffle(standalone_sampled)

    # 3. 抽聽力題
    listening_sampled: list = []
    if include_listening and listening_data:
        actual_listening = min(listening_count, len(listening_data))
        listening_sampled = random.sample(listening_data, actual_listening)

    # 4. 抽閱讀題（Part 6 + Part 7 合併，整組不拆散）
    reading_sampled: list = []
    if include_reading and reading_group_map:
        chosen_ids = random.sample(
            list(reading_group_map.keys()),
            min(reading_groups, len(reading_group_map))
        )
        for gid in chosen_ids:
            reading_sampled.extend(reading_group_map[gid])

    sampled = listening_sampled + standalone_sampled + reading_sampled
    if not sampled:
        raise HTTPException(400, detail="未選擇任何題型，請至少選一種")

    # 5. 查對應 articles
    group_ids = list({q["group_id"] for q in sampled if q.get("group_id")})
    articles_map: dict[str, dict] = {}
    if group_ids:
        try:
            art_res = supabase.table("article").select("*").in_("group_id", group_ids).execute()

            for article in art_res.data:
                articles_map[article["group_id"]] = article
        except Exception as e:
            print(f"WARNING articles failed: {e}")

    # 6. 組裝
    session_id = str(uuid.uuid4())
    questions = []
    correct_answers = {}

    for row in sampled:
        qid = str(row["question_id"])
        try:
            correct_idx = letter_to_index(row["correct_answer"])
        except ValueError as e:
            raise HTTPException(500, detail=f"題目 {qid} 的答案欄位有誤：{e}")

        gid = row.get("group_id")
        article = articles_map.get(gid) if gid else None

        audio_path = row.get("audio_path")
        audio_url = (f"{SUPABASE_URL}/storage/v1/object/public/audio/{audio_path}" if audio_path else None)
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
            group_id=gid,
            article_text=article["article_text"] if article else None,
            article_type=article["article_type"] if article else None,
            article_translation=article.get("article_translation") if article else None,
            audio_url=audio_url,
            part=row.get("part"),
        ))
        correct_answers[qid] = correct_idx

    exam_sessions[session_id] = {
        "questions":    sampled,
        "correct_answers": correct_answers,
        "articles_map": articles_map,
    }

    print(f"📝 本次測驗：聽力 {len(listening_sampled)} 題 + 單字 {len(standalone_sampled)} 題 + 閱讀 {len(reading_sampled)} 題 = 共 {len(sampled)} 題")

    return QuizSession(
        session_id=session_id,
        questions=questions,
        time_limit_seconds=900,
    )


# ════════════════════════════════════════════════
# 交卷
# ════════════════════════════════════════════════

@app.post("/api/quiz/submit", response_model=ExamResult)
def submit_quiz(payload: AnswerSubmit, user_id: str = Depends(verify_token)):
    session = exam_sessions.get(payload.session_id)
    if not session:
        raise HTTPException(404, detail="找不到此考試 session，可能已過期")

    correct_answers: dict = session["correct_answers"]
    session_questions: list = session["questions"]
    articles_map: dict = session.get("articles_map", {})

    correct_count    = 0
    wrong_count      = 0
    unanswered_count = 0
    question_results = []
    total_time       = sum(payload.time_spent_per_q.values())
    
    records_to_insert = []

    for row in session_questions:
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

        # 準備資料庫紀錄
        user_ans_letter = index_to_letter(user_ans)
        records_to_insert.append({
            "user_id": user_id,
            "question_id": qid,
            "user_answer": user_ans_letter,
            "is_correct": is_correct,
            "time_spent": payload.time_spent_per_q.get(qid, 0),
            "review_status": "needs_review" if not is_correct and user_ans is not None else None
        })

        ai_analysis = str(row.get("explanation", "解析尚未提供"))
        translation = str(row.get("translation", ""))
        raw_vocab   = str(row.get("vocabulary", ""))
        vocab_list  = [v.strip() for v in raw_vocab.replace("、", ",").split(",") if v.strip()]

        gid = row.get("group_id")
        article = articles_map.get(gid) if gid else None

        audio_path = row.get("audio_path")
        audio_url = (f"{SUPABASE_URL}/storage/v1/object/public/audio/{audio_path}" if audio_path else None)

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
            group_id=gid,
            article_text=article["article_text"] if article else None,
            article_type=article["article_type"] if article else None,
            article_translation=article.get("article_translation") if article else None,
            audio_url=audio_url,
            part=row.get("part"),
        ))

    total_q = len(session_questions)
    score   = round((correct_count / total_q) * 100) if total_q else 0
    accuracy_rate = correct_count / total_q if total_q > 0 else 0

    # 1. 寫入測驗紀錄 (exam_attempts)
    attempt_data = {
        "user_id": user_id,
        "attempt_type": payload.attempt_type or "practice",
        "total_questions": total_q,
        "correct_answers": correct_count,
        "accuracy_rate": accuracy_rate,
        "total_time_spent": total_time,
    }
    
    try:
        attempt_res = supabase.table("exam_attempts").insert(attempt_data).execute()
        if attempt_res.data:
            attempt_id = attempt_res.data[0]["id"]
            # 2. 批次寫入作答明細 (answer_records)
            for r in records_to_insert:
                r["attempt_id"] = attempt_id
            supabase.table("answer_records").insert(records_to_insert).execute()
    except Exception as e:
        print(f"⚠️  測驗紀錄存入失敗：{e}")

    del exam_sessions[payload.session_id]

    return ExamResult(
        score=score,
        correct_count=correct_count,
        wrong_count=wrong_count,
        unanswered_count=unanswered_count,
        total_time_seconds=total_time,
        question_results=question_results,
    )


# ════════════════════════════════════════════════
# 其他端點
# ════════════════════════════════════════════════

@app.get("/api/user/{user_id}/stats", response_model=UserStats)
def get_user_stats(user_id: str):
    # username
    user_res = supabase.table("users").select("username").eq("id", user_id).single().execute()
    username = user_res.data.get("username") or "使用者"

    # 從 exam_attempts 表拿作答紀錄
    attempts_res = supabase.table("exam_attempts") \
        .select("total_questions, accuracy_rate, created_at, total_time_spent") \
        .eq("user_id", user_id) \
        .order("created_at") \
        .execute()
    attempts = attempts_res.data or []

    # 預估分數
    total_questions = sum(a.get("total_questions", 0) for a in attempts)
    accuracies = [float(a["accuracy_rate"]) for a in attempts if a.get("accuracy_rate") is not None]
    estimated_score = round(sum(accuracies) / len(accuracies) * 990) if accuracies else 0

    # 平均作答時間
    total_time = sum(a.get("total_time_spent") or 0 for a in attempts)
    # total_q = sum(a.get("total_questions", 0) for a in attempts)
    # avg_time_per_q = round(total_time / total_q, 1) if total_q > 0 else 0
    avg_time_per_q = round(total_time / len(attempts), 1) if attempts else 0

    # 近五次測驗折線圖
    recent_attempts = attempts[-5:] if len(attempts) > 5 else attempts
    score_history = [
        {
            "month": a["created_at"][5:10].replace("-", "/"),
            "score": round(float(a["accuracy_rate"]) * 990)
        }
        for a in recent_attempts
    ]

    # 雷達圖
    records_res = supabase.table("answer_records") \
        .select("is_correct, questions!inner(skill_tag)") \
        .eq("user_id", user_id) \
        .execute()
    records = records_res.data or []
    tag_stats = defaultdict(lambda: {"correct": 0, "total": 0})
    for r in records:
        raw_tag = r["questions"]["skill_tag"]
        category = classify_skill_tag(raw_tag)
        tag_stats[category]["total"] += 1
        if r["is_correct"]:
            tag_stats[category]["correct"] += 1

    categories = ["文法", "單字", "閱讀理解", "聽力", "推論能力", "商業用語"]
    radar_data = [
        {
            "label": cat,
            "value": round(tag_stats[cat]["correct"] / tag_stats[cat]["total"] * 100)
                    if tag_stats[cat]["total"] > 0 else 0,
            # "value": tag_stats[cat]["correct"],
        }
        for cat in categories
    ]
    
    return UserStats(
        username=username,
        total_questions=total_questions,
        estimated_score=estimated_score,
        friend_rank="-",
        avg_time_per_q=avg_time_per_q,
        score_history=score_history if score_history else [{"month": "尚無資料", "score": 0}],
        radar_data=radar_data,
    )


@app.post("/api/quiz/generate-practice")
def generate_practice(payload: PracticeRequest):
    question_id = payload.question_id
    if not questions_data:
        raise HTTPException(503, detail="題庫未載入")
    all_data = vocalvulary_data + reading_data + listening_data
    original = [q for q in all_data if str(q.get("question_id")) == question_id]
    if not original:
        raise HTTPException(404, detail=f"找不到題目 {question_id}")
    tag = original[0].get("skill_tag")
    part = original[0].get("part")
    current_group = original[0].get("group_id")

    # Part 3/4：同一對話有多題，改為抽另一組對話（不同 group_id）
    if part in (3, 4):
        # 找所有 Part 3/4 的 group_id，排除目前這組
        other_groups: dict[str, list] = {}
        for q in all_data:
            if q.get("part") == part and q.get("group_id") and q.get("group_id") != current_group:
                other_groups.setdefault(q["group_id"], []).append(q)
        if not other_groups:
            raise HTTPException(404, detail="找不到其他對話組可供練習")
        chosen_gid = random.choice(list(other_groups.keys()))
        group_questions = other_groups[chosen_gid]
        # 取第一題作為代表（音檔相同）
        row = group_questions[0]
    else:
        same_tag = [q for q in all_data if q.get("skill_tag") == tag and q.get("part") == part and str(q.get("question_id")) != question_id]
        if not same_tag:
            raise HTTPException(404, detail="找不到相同考點的其他題目")
        row = random.choice(same_tag)
    # 閱讀題：查對應文章
    gid = row.get("group_id")
    article = None
    if gid:
        try:
            art_res = supabase.table("article").select("*").eq("group_id", gid).execute()
            if art_res.data:
                article = art_res.data[0]
        except Exception as e:
            print(f"WARNING practice article failed: {e}")
    # 聽力題：組 audio_url
    audio_path = row.get("audio_path")
    audio_url = (
        f"{SUPABASE_URL}/storage/v1/object/public/audio/{audio_path}"
        if audio_path else None
    )
    return {
        "id":                str(row.get("question_id", "")),
        "tag":               str(row.get("skill_tag", "")),
        "text":              str(row.get("question_text", "")),
        "part":              row.get("part"),
        "audio_url":         audio_url,
        "correct_index":     letter_to_index(row.get("correct_answer", "A")),
        "explanation":       str(row.get("explanation", "")),
        "translation":       str(row.get("translation", "")),
        "article_text":      article["article_text"] if article else None,
        "article_type":      article["article_type"] if article else None,
        "options": [
            str(row.get("option_a", "")),
            str(row.get("option_b", "")),
            str(row.get("option_c", "")),
            str(row.get("option_d", "")),
        ],
    }