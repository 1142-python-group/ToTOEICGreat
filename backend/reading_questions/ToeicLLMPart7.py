import json
import pandas as pd
import os
import uuid
import time
import random
import re
from collections import deque
import csv  
from google import genai
from google.genai import types
from google.genai.errors import APIError

# [備用] 如果未來要寫入向量資料庫，再把這行解開
# import chromadb

# ---------------------------------------------------------
# 1. 題庫與設定區 (Part 7 專屬)
# ---------------------------------------------------------
toeic_scenarios = [
    "辦公室設備故障與報修流程", "跨部門會議時間協調與議程安排", "內部系統升級與電子郵件公告",
    "新進員工招募面試與薪資談判", "公司內部教育訓練與講座報名", "跨國企業合約簽訂與條款談判",
    "尋找新供應商與產品報價單", "貨物延遲出貨與物流追蹤", "訂單錯誤處理與退換貨流程",
    "新產品研發上市與市場調查", "公關危機處理與新聞稿發布", "消費者滿意度問卷與數據分析",
    "國際航班預訂、延誤與行李遺失", "飯店房間預訂、升等與客房服務", "商業辦公室租賃與續約談判",
    "網路資安漏洞與密碼重置公告", "消費者電子產品的操作手冊說明"
]

article_types = [
    "Email (電子郵件)", "Notice (公告)", "Memo (內部備忘錄)", 
    "Advertisement (廣告)", "Article (文章/報導)", "Letter (信件)"
]

# 🛡️ [修正] API Key 資安優化：優先從環境變數讀取
# 請在系統環境變數設定 GEMINI_API_KEY_1 與 GEMINI_API_KEY_2
env_key_1 = os.getenv("GEMINI_API_KEY_1")
env_key_2 = os.getenv("GEMINI_API_KEY_2")

# 如果環境變數有抓到，就使用環境變數；若無，可暫時在這裡填寫測試用 Key (強烈建議測試完刪除)
API_KEYS = [key for key in [env_key_1, env_key_2] if key]
if not API_KEYS:
    print("⚠️ 警告：未從環境變數偵測到 API Key。")
    API_KEYS = [
        "填入你的api key1",
        "填入你的api key2"
    ]

article_columns = ["group_id", "article_type", "article_text", "article_translation", "vocabulary"]

question_columns = [
    "question_id", "group_id", "question_text", "option_a", "option_b", 
    "option_c", "option_d", "correct_answer", "explanation", "skill_tag", 
    "translation", "vocabulary", "part"
]

# ⚙️ [新增] 安全限制：每次執行最多生成的文章篇數，避免無限迴圈耗盡 API 額度
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
    # 清理換行符號防破版
    df = df.astype(str).replace({'\n': ' ', '\r': ' '}, regex=True)
    write_header = not os.path.exists(filename)
    df.to_csv(
        filename, 
        mode='a', 
        header=write_header, 
        index=False, 
        encoding="utf-8-sig",
        sep=',',
        quoting=csv.QUOTE_ALL # 強制幫所有欄位加上雙引號防護
    )

current_key_index = 0
total_article_groups = 0
total_questions = 0

recent_history = deque(maxlen=10) 
history_file = "history_scenarios_part7.txt" 

if os.path.exists(history_file):
    with open(history_file, "r", encoding="utf-8") as f:
        past_scenarios = f.read().splitlines()
        for scenario in past_scenarios[-10:]:
            recent_history.append(scenario)
    print(f"🧠 已恢復記憶！系統記得最近出過的 {len(recent_history)} 種情境。")
else:
    print("🧠 這是第一次執行，尚無歷史記憶。")

# ---------------------------------------------------------
# 3. 核心迴圈邏輯
# ---------------------------------------------------------
client = genai.Client(api_key=API_KEYS[current_key_index])

# 加入 total_article_groups < MAX_GENERATIONS 的條件，避免無限生成
while current_key_index < len(API_KEYS) and total_article_groups < MAX_GENERATIONS:
    print(f"\n[目前使用 Key: {current_key_index + 1}/{len(API_KEYS)}] 準備出題中... (進度: {total_article_groups + 1}/{MAX_GENERATIONS})")
    
    current_scenario = random.choice(toeic_scenarios)
    current_type = random.choice(article_types)
    blacklist_str = "、".join(recent_history) if recent_history else "無"

    prompt = f"""
你是一個專業的多益 (TOEIC) 命題老師。請幫我生成「符合 ETS 真實考試難度」的 Part 7 單篇文章閱讀測驗。

【本次命題嚴格限制條件】
1. 數量要求：生成 1 篇長度適中（約 120-180 字）的英文文章，以及 **3 題** 相關的單選題。
2. 指定情境：文章內容必須是【{current_scenario}】。
3. 文章類型：這篇文章的格式必須是【{current_type}】。
4. 題型分配：3 題題目中，請務必包含「主旨題」、「細節題」、「推論題」各一題。
5. 反抄襲與限制：絕對不可以包含以下情境：[{blacklist_str}]。請確保句型具備商業正式感。

請嚴格依照以下的 JSON 格式回傳，絕對不要加入 markdown 標記 (如 ```json) 或任何其他文字說明：
{{
  "article_type": "{current_type}",
  "article_text": "英文文章內容",
  "article_translation": "整篇英文文章的順暢繁體中文翻譯",
  "vocabulary": "請挑選「文章中」 4-5 個最具商業價值的多益單字。格式請嚴格統一為：【英文單字 (詞性) - 繁體中文解釋】，多個單字請用頓號分隔。",
  "questions": [
    {{
      "question_text": "第 1 題英文題目內容 (主旨題)",
      "option_a": "選項 A", "option_b": "選項 B", "option_c": "選項 C", "option_d": "選項 D",
      "correct_answer": "A/B/C/D",
      "explanation": "繁體中文詳細解析，說明能在文章哪一句找到線索",
      "translation": "題目與四個選項的完整繁體中文翻譯",
      "vocabulary": "請挑選「這題的題目或選項中」1-2 個重要單字。格式：【英文單字 (詞性) - 繁體中文解釋】",
      "skill_tag": "閱讀-主旨題"
    }},
    {{
      "question_text": "第 2 題英文題目內容 (細節題)",
      "option_a": "選項 A", "option_b": "選項 B", "option_c": "選項 C", "option_d": "選項 D",
      "correct_answer": "A/B/C/D",
      "explanation": "繁體中文詳細解析",
      "translation": "題目與四個選項的完整繁體中文翻譯",
      "vocabulary": "請挑選「這題的題目或選項中」1-2 個重要單字。格式：【英文單字 (詞性) - 繁體中文解釋】",
      "skill_tag": "閱讀-細節題"
    }},
    {{
      "question_text": "第 3 題英文題目內容 (推論題)",
      "option_a": "選項 A", "option_b": "選項 B", "option_c": "選項 C", "option_d": "選項 D",
      "correct_answer": "A/B/C/D",
      "explanation": "繁體中文詳細解析",
      "translation": "題目與四個選項的完整繁體中文翻譯",
      "vocabulary": "請挑選「這題的題目或選項中」1-2 個重要單字。格式：【英文單字 (詞性) - 繁體中文解釋】",
      "skill_tag": "閱讀-推論題"
    }}
  ]
}}
"""
    try:
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite-preview',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=1.2  
            )
        )
        
        try:
            # 🛡️ [優化] 利用正則表達式強制清除可能夾帶的 Markdown 標記，確保能被 json.loads 解析
            clean_text = re.sub(r'^```(?:json)?\s*|\s*```$', '', response.text.strip(), flags=re.MULTILINE)
            data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON 解析失敗: {e}，捨棄此回合，重新請求...")
            time.sleep(2)
            continue
            
        # ---------------------------------------------------------
        # 4. 資料處理與雙檔寫入
        # ---------------------------------------------------------
        group_id = get_short_id("G") 
        
        # 整理文章資料
        article_record = {
            "group_id": group_id,
            "article_type": data.get("article_type", current_type),
            "article_text": data.get("article_text", ""),
            "article_translation": data.get("article_translation", ""), 
            "vocabulary": data.get("vocabulary", "")
        }
        df_article = pd.DataFrame([article_record])[article_columns]

        # 整理題目資料
        question_records = []

        for q in data.get("questions", []):
            q["question_id"] = get_short_id("SQ")
            q["group_id"] = group_id 
            q["part"] = 7
            q["translation"] = q.get("translation", "")
            q["vocabulary"] = q.get("vocabulary", "")
            
            # 確保所有指定欄位都在字典中
            for col in question_columns:
                if col not in q:
                    q[col] = ""
                    
            question_records.append(q)
            
        # 安全轉換成 DataFrame
        df_questions = pd.DataFrame(question_records)[question_columns]
        
        # 執行存檔
        save_to_csv(df_article, "articles.csv")
        save_to_csv(df_questions, "questions.csv")
        
        total_article_groups += 1
        total_questions += len(df_questions)
        
        print(f"✅ 成功寫入！情境：【{current_scenario}】。")
        print(f"   -> 新增 1 篇文章 ({group_id}) 與 {len(df_questions)} 題。累積: {total_questions} 題")
        
        recent_history.append(current_scenario)
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(current_scenario + "\n")
            
        time.sleep(8) 

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
        print(f"⚠️ 發生未預期的錯誤: {e}")
        time.sleep(10)

print(f"\n🎉 執行完畢！本次總共生成了 {total_article_groups} 篇文章與 {total_questions} 道題目！")
