from fastapi import APIRouter, Depends, HTTPException
import json
import uuid
import os
import re
from dotenv import load_dotenv
from database import supabase
from models import QuizSession, Question
from routers.account_service.authen import verify_token
from google import genai
from google.genai import types

load_dotenv()
router = APIRouter(prefix="/api/quiz", tags=["Adaptive Learning"])

# 初始化 Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("缺少 GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_API_KEY)

def get_short_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:6]}"

def extract_json(raw_text):
    match = re.search(r'\{.*\}', raw_text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("找不到合法的 JSON 結構")

@router.post("/generate-history-practice", response_model=QuizSession)
async def generate_history_practice(user_id: str = Depends(verify_token)):
    # ==========================================
    # 1. 撈取最近 10 筆錯題紀錄 (Join 查詢)
    # ==========================================
    res = supabase.table("answer_records").select(
        "questions!inner(question_text, skill_tag, vocabulary)"
    ).eq("user_id", user_id).eq("is_correct", False).eq("review_status", "needs_review").order("create_at", desc=True).limit(10).execute()
    
    if not res.data:
        raise HTTPException(status_code=400, detail="太棒了！您目前沒有需要複習的錯題。")

    # 整理給 LLM 的參考情境
    error_context = "\n".join([
        f"錯題考點: {r['questions']['skill_tag']} | 原錯題單字: {r['questions']['vocabulary']}" 
        for r in res.data
    ])

    # ==========================================
    # 2. 嚴格的混合出題 Prompt (3 題 Part5 + 1文2題 Part7)
    # ==========================================
    prompt = f"""
你是一個專業的多益老師。學生最近在以下考點答錯了：
{error_context}

請針對這些弱點，生成一份包含 5 題的「高難度真實多益」特訓卷。
包含：3 題 Part 5 (單選填空) + 1 篇 Part 7 商業文章 (約120字) 配 2 題閱讀測驗。

請嚴格回傳以下 JSON 格式：
{{
  "part5": [
    {{
      "question_text": "第1題英文題目", "option_a": "A", "option_b": "B", "option_c": "C", "option_d": "D",
      "correct_answer": "A/B/C/D", "explanation": "繁體中文解析", "translation": "翻譯", "vocabulary": "單字 (詞性) - 說明", "skill_tag": "考點"
    }} // 共 3 個物件
  ],
  "part7": {{
    "article_type": "Email",
    "article_text": "英文文章內容",
    "article_translation": "文章翻譯",
    "vocabulary": "文章重點單字",
    "questions": [
      {{
         "question_text": "閱讀題1", "option_a": "A", "option_b": "B", "option_c": "C", "option_d": "D",
         "correct_answer": "A/B/C/D", "explanation": "解析", "translation": "翻譯", "skill_tag": "閱讀-主旨題"
      }} // 共 2 個物件
    ]
  }}
}}
"""
    
    # ==========================================
    # 3. 呼叫 LLM
    # ==========================================
    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.5, max_output_tokens=8192)
        )
        ai_data = extract_json(response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 出題失敗: {e}")

    # ==========================================
    # 4. 準備寫入資料庫 (Supabase Upsert)
    # ==========================================
    db_questions_to_insert = []
    frontend_questions = []

    # 處理 Part 5
    for q in ai_data.get("part5", []):
        qid = get_short_id("SQ")
        
        # 準備存入 DB
        db_questions_to_insert.append({
            "question_id": qid, "group_id": None, "part": 5,
            "question_text": q["question_text"], "option_a": q["option_a"], "option_b": q["option_b"], 
            "option_c": q["option_c"], "option_d": q["option_d"], "correct_answer": q["correct_answer"], 
            "explanation": q["explanation"], "translation": q["translation"], "vocabulary": q["vocabulary"], "skill_tag": q["skill_tag"]
        })
        
        # 準備給前端 (使用隊友定義的 model)
        frontend_questions.append(Question(
            id=qid, tag=q["skill_tag"], text=q["question_text"],
            options=[q["option_a"], q["option_b"], q["option_c"], q["option_d"]]
        ))

    # 處理 Part 7
    p7 = ai_data.get("part7", {})
    group_id = get_short_id("G")
    
    # 將文章寫入 articles 表
    supabase.table("articles").insert({
        "group_id": group_id, "article_type": p7.get("article_type"), 
        "article_text": p7.get("article_text"), "article_translation": p7.get("article_translation"), "vocabulary": p7.get("vocabulary")
    }).execute()

    for q in p7.get("questions", []):
        qid = get_short_id("SQ")
        
        db_questions_to_insert.append({
            "question_id": qid, "group_id": group_id, "part": 7,
            "question_text": q["question_text"], "option_a": q["option_a"], "option_b": q["option_b"], 
            "option_c": q["option_c"], "option_d": q["option_d"], "correct_answer": q["correct_answer"], 
            "explanation": q["explanation"], "translation": q["translation"], "vocabulary": "", "skill_tag": q["skill_tag"]
        })

        frontend_questions.append(Question(
            id=qid, tag=q["skill_tag"], text=q["question_text"],
            options=[q["option_a"], q["option_b"], q["option_c"], q["option_d"]],
            article_text=p7.get("article_text"), # 綁定文章內容給前端渲染
            article_type=p7.get("article_type")
        ))

    # 整批寫入 questions 表
    supabase.table("questions").insert(db_questions_to_insert).execute()

    # ==========================================
    # 5. 回傳給前端 (建立 Session)
    # ==========================================
    # 注意：這裡我們要把正確答案存到隊友 main.py 裡的 exam_sessions 記憶體中
    # 所以需要稍微繞一下，或者你可以直接在 main.py import 這個 router 並更新 dict
    session_id = str(uuid.uuid4())
    correct_answers_dict = {
        q["question_id"]: {"A":0, "B":1, "C":2, "D":3}.get(q["correct_answer"].upper(), 0) 
        for q in db_questions_to_insert
    }

    # 🔥 關鍵：更新 main.py 的記憶體字典 (請確保有正確從 main import)
    from main import exam_sessions, questions_data 
    
    exam_sessions[session_id] = {
        "questions": db_questions_to_insert, 
        "correct_answers": correct_answers_dict
    }
    
    # 順手更新題庫快取，這樣 /api/quiz/start 以後才抽得到這些新題目！
    questions_data.extend(db_questions_to_insert)

    return QuizSession(
        session_id=session_id,
        questions=frontend_questions,
        time_limit_seconds=900
    )