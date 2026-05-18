import json
import pandas as pd
import os
import uuid
import time
import random
import csv  
from collections import deque
from google import genai
from google.genai import types
from google.genai.errors import APIError

# ---------------------------------------------------------
# 1. 題庫與設定區 (Part 6 專屬)
# ---------------------------------------------------------
toeic_scenarios = [
    "Email (跨部門溝通或對外客戶電子郵件)",
    "Notice/Announcement (公司內部人事或政策公告)",
    "Advertisement (新產品發布或促銷廣告)",
    "Article/News (商業新聞、產業趨勢文章)",
    "Memo (內部備忘錄、會議紀錄摘要)",
    "Letter (正式的商業書信、投訴信或邀請函)"
]

# 🛡️ API Key 優先從環境變數讀取
env_key_1 = os.getenv("GEMINI_API_KEY_1")
env_key_2 = os.getenv("GEMINI_API_KEY_2")

API_KEYS = [key for key in [env_key_1, env_key_2] if key]
if not API_KEYS:
    print("⚠️ 警告：未從環境變數偵測到 API Key。")
    API_KEYS = [
        "AIzaSyDi3Uds-CnPAlzL7h6hDEmGpZnzflo_pQI",
        "YOUR_API_KEY_2_HERE"
    ]

# 嚴格對齊你提供的 CSV 格式
article_columns = ["group_id", "article_type", "article_text", "article_translation", "vocabulary"]

question_columns = [
    "question_id", "group_id", "question_text", "option_a", "option_b", 
    "option_c", "option_d", "correct_answer", "explanation", "skill_tag", 
    "translation", "vocabulary", "part"
]

MAX_GENERATIONS = 100

# ---------------------------------------------------------
# 2. 初始化與共用函式
# ---------------------------------------------------------
def get_short_id(prefix):
    """生成 6 碼的隨機唯一 ID"""
    return f"{prefix}_{uuid.uuid4().hex[:6]}"

def save_to_csv(df, filename):
    """通用的防彈 CSV 存檔函式"""
    if df.empty: return
    df = df.astype(str).replace({'\n': ' ', '\r': ' '}, regex=True)
    write_header = not os.path.exists(filename)
    df.to_csv(
        filename, 
        mode='a', 
        header=write_header, 
        index=False, 
        encoding="utf-8-sig",
        sep=',',
        quoting=csv.QUOTE_ALL
    )

current_key_index = 0
total_article_groups = 0
total_questions = 0

recent_history = deque(maxlen=10) 
history_file = "history_scenarios_part6.txt" 

if os.path.exists(history_file):
    with open(history_file, "r", encoding="utf-8") as f:
        past_scenarios = f.read().splitlines()
        for scenario in past_scenarios[-10:]:
            recent_history.append(scenario)
    print(f"🧠 已恢復記憶！系統記得最近出過的 {len(recent_history)} 種情境。")
else:
    print("🧠 這是第一次執行，尚無歷史記憶。")

client = genai.Client(api_key=API_KEYS[current_key_index])

# ---------------------------------------------------------
# 3. 核心迴圈邏輯
# ---------------------------------------------------------
while current_key_index < len(API_KEYS) and total_article_groups < MAX_GENERATIONS:
    print(f"\n[目前使用 Key: {current_key_index + 1}/{len(API_KEYS)}] 準備出題中... (進度: {total_article_groups + 1}/{MAX_GENERATIONS})")
    
    current_scenario = random.choice(toeic_scenarios)
    current_type = current_scenario.split(" ")[0] 
    blacklist_str = "、".join(recent_history) if recent_history else "無"

    prompt = f"""
你是一個專業的多益 (TOEIC) 命題老師。請幫我生成「符合 ETS 真實考試難度」的 Part 6 (Text Completion 段落填空) 題組。

【本次命題嚴格限制條件】
1. 數量要求：生成 1 篇長度適中（約 100-150 字）的商業英文文章，並在文章中剛好設計 4 個挖空，標記為 ___1___, ___2___, ___3___, ___4___。
2. 指定情境：文章內容必須是【{current_scenario}】。
3. 題型分配：必須提供 4 題單選題。前 3 題為單字/文法填空，第 4 題必須是「完整句子插入題 (Sentence Insertion)」。
4. 反抄襲與限制：絕對不可以包含以下情境：[{blacklist_str}]。

請嚴格依照以下的 JSON 格式回傳，絕對不要加入任何說明文字：
{{
  "article_type": "{current_type}",
  "article_text": "英文文章內容 (必須包含 ___1___ 到 ___4___ 四個挖空)",
  "article_translation": "整篇英文文章的順暢繁體中文翻譯",
  "vocabulary": "挑選整篇文章 3-5 個多益單字。格式：【英文單字 (詞性) - 繁體中文解釋】",
  "questions": [
    {{
      "question_text": "Choose the best word or phrase for blank (1).",
      "option_a": "選項 A", "option_b": "選項 B", "option_c": "選項 C", "option_d": "選項 D",
      "correct_answer": "A/B/C/D",
      "explanation": "繁體中文詳細解析",
      "translation": "本題挖空處所在句子的完整繁體中文翻譯",
      "vocabulary": "選項重點單字。格式：【英文單字 (詞性) - 繁體中文解釋】",
      "skill_tag": "文法-時態"
    }},
    {{
      "question_text": "Choose the best word or phrase for blank (2).",
      "option_a": "選項 A", "option_b": "選項 B", "option_c": "選項 C", "option_d": "選項 D",
      "correct_answer": "A/B/C/D",
      "explanation": "繁體中文詳細解析",
      "translation": "本題挖空處所在句子的完整繁體中文翻譯",
      "vocabulary": "選項重點單字",
      "skill_tag": "單字-名詞"
    }},
    {{
      "question_text": "Choose the best word or phrase for blank (3).",
      "option_a": "選項 A", "option_b": "選項 B", "option_c": "選項 C", "option_d": "選項 D",
      "correct_answer": "A/B/C/D",
      "explanation": "繁體中文詳細解析",
      "translation": "本題挖空處所在句子的完整繁體中文翻譯",
      "vocabulary": "選項重點單字",
      "skill_tag": "片語-動詞片語"
    }},
    {{
      "question_text": "Choose the best sentence to complete blank (4).",
      "option_a": "長句子選項 A", "option_b": "長句子選項 B", "option_c": "長句子選項 C", "option_d": "長句子選項 D",
      "correct_answer": "A/B/C/D",
      "explanation": "繁體中文詳細解析，說明為什麼選這個句子",
      "translation": "四個長句子選項的完整繁體中文翻譯",
      "vocabulary": "選項重點單字",
      "skill_tag": "閱讀-句子插入"
    }}
  ]
}}
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=1.0 
            )
        )
        
        try:
            # 🛡️ 終極防護：使用字串乘法來產生 Markdown 標記，徹底避開介面 Bug
            clean_text = response.text.strip()
            md_prefix = "`" * 3 + "json"
            md_suffix = "`" * 3
            
            if clean_text.startswith(md_prefix):
                clean_text = clean_text[len(md_prefix):]
            elif clean_text.startswith(md_suffix):
                clean_text = clean_text[3:]
                
            if clean_text.endswith(md_suffix):
                clean_text = clean_text[:-3]
                
            clean_text = clean_text.strip()
            data = json.loads(clean_text)
            
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON 解析失敗: {e}，捨棄此回合，重新請求...")
            time.sleep(2)
            continue
            
        group_id = get_short_id("G") 
        
        article_record = {
            "group_id": group_id,
            "article_type": data.get("article_type", current_type),
            "article_text": data.get("article_text", ""),
            "article_translation": data.get("article_translation", ""), 
            "vocabulary": data.get("vocabulary", "")
        }
        df_article = pd.DataFrame([article_record])[article_columns]

        question_records = []
        for q in data.get("questions", []):
            q["question_id"] = get_short_id("SQ")
            q["group_id"] = group_id 
            q["part"] = 6
            q["translation"] = q.get("translation", "")
            q["vocabulary"] = q.get("vocabulary", "")
            q["skill_tag"] = q.get("skill_tag", "")
            
            for col in question_columns:
                if col not in q:
                    q[col] = ""
                    
            question_records.append(q)
            
        df_questions = pd.DataFrame(question_records)[question_columns]
        
        save_to_csv(df_article, "articles.csv")
        save_to_csv(df_questions, "questions.csv")
        
        total_article_groups += 1
        total_questions += len(df_questions)
        
        print(f"✅ 成功寫入！情境：【{current_scenario}】。")
        print(f"   -> 新增 1 篇文章 ({group_id}) 與 {len(df_questions)} 題。累積: {total_questions} 題")
        
        recent_history.append(current_scenario)
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(current_scenario + "\n")
            
        time.sleep(5) 

    except APIError as e:
        error_msg = e.message.lower()
        if "high demand" in error_msg or "503" in str(e.code) or "unavailable" in error_msg:
            print("⏳ 警告：Google 伺服器目前大塞車或配額受限！休息 60 秒...")
            time.sleep(60)
            continue 
        else:
            print(f"❌ 警告：這把 API Key 發生錯誤！\n詳細訊息: {e.message}")
            current_key_index += 1
            if current_key_index < len(API_KEYS):
                print(f"🔄 正在切換到第 {current_key_index + 1} 把 Key...")
                client = genai.Client(api_key=API_KEYS[current_key_index])
                time.sleep(5) 
            else:
                print("🛑 所有 API Key 都已嘗試完畢！")
                break
                
    except Exception as e:
        print(f"⚠️ 發生未預期的錯誤: {str(e)}")
        time.sleep(10)

print(f"\n🎉 執行完畢！本次總共生成了 {total_article_groups} 篇 Part 6 文章與 {total_questions} 道題目！")