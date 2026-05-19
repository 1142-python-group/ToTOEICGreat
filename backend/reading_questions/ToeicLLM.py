import json
import pandas as pd
import os
import uuid
import time
import random
from collections import deque
import chromadb

# 引入 Google GenAI SDK
from google import genai
from google.genai import types
from google.genai.errors import APIError

# ---------------------------------------------------------
# 1. 題庫與設定區
# ---------------------------------------------------------
toeic_scenarios = [
    "辦公室設備故障與報修流程", "跨部門會議時間協調與議程安排", "辦公用品耗材採購與庫存盤點", "內部系統升級與電子郵件公告",
    "新進員工招募面試與薪資談判", "員工績效考核與升遷公告", "員工退休歡送會與離職交接", "公司內部教育訓練與講座報名",
    "跨國企業合約簽訂與條款談判", "公司併購或組織架構重組", "商業合作提案與企劃書審閱", "營業時間更改或店面搬遷通知",
    "尋找新供應商與產品報價單", "貨物延遲出貨與物流追蹤", "訂單錯誤處理與退換貨流程", "大宗採購的批量折扣與發票開立",
    "工廠生產線排程與原物料短缺", "產品品質控管 (QC) 與瑕疵回收", "廠房安全檢查與公安規範更新", "新技術導入與自動化設備評估",
    "新產品研發上市與市場調查", "公關危機處理與新聞稿發布", "參展報名與攤位佈置規劃", "消費者滿意度問卷與數據分析",
    "季度財務報表與預算刪減", "企業貸款申請與銀行業務", "個人稅務申報與會計帳目核對", "差旅費用報銷與單據審查",
    "國際航班預訂、延誤與行李遺失", "飯店房間預訂、升等與客房服務", "機場接駁車與租車服務安排", "商務簽證申請與出差行程表規劃",
    "商務午餐預訂與特殊飲食需求", "大型尾牙或企業晚宴外燴服務", "劇院展覽門票預購與退款規定", "餐廳衛生檢查與菜單價格調整",
    "商業辦公室租賃與續約談判", "物業管理與水電修繕工程", "建築工地施工進度與噪音投訴", "辦公室空間重新裝潢與動線規劃",
    "員工年度健康檢查安排", "醫療保險理賠申請與給付", "牙醫或診所預約時間更改", "生技藥廠新藥實驗與發表",
    "軟體訂閱制合約更新與伺服器維護", "網路資安漏洞與密碼重置公告", "消費者電子產品的操作手冊說明", "實驗室儀器操作規範與保養"
]

# ⚠️ 確保此處標籤與 CSV / ChromaDB 內的標籤完全一致
grammar_focus = [
    "文法-動詞時態", "文法-詞性變化", "文法-分詞構句", "文法-介系詞", 
    "文法-連接詞", "文法-關係代名詞", "文法-動名詞", "文法-被動語態",
    "單字-動詞", "單字-名詞", "單字-形容詞", "單字-副詞"
]

API_KEYS = [
    "AIzaSyDAcOkm01g3uJSpoDZGsEFtlvazUCWeN0Y",
    "AIzaSyBwvdGKuvy3AvzZq1Iqg4Jc19rUTt6GABg"
]

# ⚠️ 你確認過的最正確輸出欄位順序
question_columns = [
    "question_id", "group_id", "question_text", "option_a", "option_b", 
    "option_c", "option_d", "correct_answer", "explanation", "skill_tag", 
    "translation", "vocabulary"
]

# ---------------------------------------------------------
# 2. 初始化資料庫與記憶機制
# ---------------------------------------------------------
print("🔌 正在連接向量資料庫...")
chroma_client = chromadb.PersistentClient(path="./toeic_chroma_db")
collection = chroma_client.get_or_create_collection(name="real_toeic_collection")

def get_short_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:6]}"

current_key_index = 0
total_generated = 0

recent_history = deque(maxlen=10) 
history_file = "history_scenarios.txt" 

if os.path.exists(history_file):
    with open(history_file, "r", encoding="utf-8") as f:
        past_scenarios = f.read().splitlines()
        for scenario in past_scenarios[-10:]:
            recent_history.append(scenario)
    print(f"🧠 已恢復記憶！系統記得最近出過的 {len(recent_history)} 種情境。")
else:
    print("🧠 這是第一次執行，尚無歷史記憶。")

print(f"🚀 啟動自動化生題程式！共有 {len(API_KEYS)} 把 API Key 待命。")

# ---------------------------------------------------------
# 3. 核心迴圈邏輯
# ---------------------------------------------------------
client = genai.Client(api_key=API_KEYS[current_key_index])

while current_key_index < len(API_KEYS):
    print(f"\n[目前使用 Key: {current_key_index + 1}/{len(API_KEYS)}] 準備出題中...")
    
    current_scenario = random.choice(toeic_scenarios)
    current_grammar = random.choice(grammar_focus)
    blacklist_str = "、".join(recent_history) if recent_history else "無"

    # ---------------------------------------------------------
    # 🌟 RAG 檢索階段 (Retrieval)
    # ---------------------------------------------------------
    print(f"🔍 正在資料庫尋找【{current_grammar}】的真實考題作為範本...")
    rag_examples_str = ""
    try:
        query_embedding = client.models.embed_content(
            model='gemini-embedding-001',
            contents=f"考點：{current_grammar}"
        ).embeddings[0].values

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=2, 
            where={"skill_tag": current_grammar} 
        )
        
        if results['metadatas'][0]:
            rag_examples_str = "【真實多益考題範例參考】\n"
            for i, meta in enumerate(results['metadatas'][0]):
                rag_examples_str += f"範例 {i+1}:\n"
                rag_examples_str += f"- 題目: {meta['question_text']}\n"
                rag_examples_str += f"- 選項: {meta['options']}\n"
                rag_examples_str += f"- 答案: {meta['correct_answer']}\n"
                rag_examples_str += f"- 解析: {meta['explanation']}\n\n"
            print("✅ 成功從資料庫提取範本！")
        else:
            rag_examples_str = "【提示】資料庫目前缺乏此考點的真實範例，請依據 ETS 標準自行發揮。"
            print("⚠️ 資料庫尚無此考點範例，由 LLM 自行發揮。")
            
    except Exception as e:
        print(f"⚠️ 資料庫檢索失敗 ({e})，跳過 RAG 直接生成。")

    # ---------------------------------------------------------
    # 🌟 生成階段 (Generation) - 專注於 Part 5
    # ---------------------------------------------------------
    prompt = f"""
你是一個專業的多益 (TOEIC) 命題老師。請幫我生成「符合 ETS 真實考試難度」的 Part 5 單選題。

{rag_examples_str}

【本次命題嚴格限制條件】
1. 數量與題型：請生成 **4 題** 「Part 5 單選題」。
2. 指定情境：所有題目的情境必須是【{current_scenario}】。
3. 指定考點：所有題目的考點必須側重於【{current_grammar}】。
4. 反抄襲指令：請學習上方真實範例的「文法難度」、「句型長度」與「誘答選項設計」。但【絕對禁止】使用範例中的具體劇情、主詞或動詞，請務必使用全新的商業情境單字造句。
5. 情境黑名單：絕對不可以包含以下情境或相關單字：[{blacklist_str}]。

請嚴格依照以下的 JSON 格式回傳，不要加入任何其他文字。注意：因為只生成單選題，請不要生成 question_groups 陣列。
{{
  "single_questions": [
    {{
      "question_text": "英文題目內容 (需挖空)",
      "option_a": "選項 A",
      "option_b": "選項 B",
      "option_c": "選項 C",
      "option_d": "選項 D",
      "correct_answer": "A/B/C/D",
      "explanation": "繁體中文詳細解析，說明正確理由與錯誤選項為何錯",
      "translation": "整句繁體中文翻譯",
      "vocabulary": "請嚴格統一使用此格式：【英文單字 (詞性) - 繁體中文解釋】，多個單字請用頓號分隔。範例：revenue (n.) - 營收、implement (v.) - 實施。列出 2-3 個重點單字。",
      "skill_tag": "{current_grammar}"
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
            data = json.loads(response.text)
        except json.JSONDecodeError:
            print("⚠️ LLM 回傳格式錯誤 (非 JSON)，捨棄此回合，重新請求...")
            time.sleep(2)
            continue
            
        # ---------------------------------------------------------
        # 4. 資料處理與寫入 CSV (只處理 Part 5)
        # ---------------------------------------------------------
        single_qs = []

        for q in data.get("single_questions", []):
            q["question_id"] = get_short_id("SQ")
            q["group_id"] = "" # Part 5 沒有題組 ID
            q.setdefault("translation", "")
            q.setdefault("vocabulary", "")
            single_qs.append(q)

        df_questions = pd.DataFrame(single_qs)
        
        # 確保缺失欄位被補齊，並且順序與 question_columns 一致
        for col in question_columns:
            if col not in df_questions.columns and not df_questions.empty:
                df_questions[col] = ""

        if not df_questions.empty: 
            df_questions = df_questions[question_columns]

        questions_file = "questions.csv"
        write_header_q = not os.path.exists(questions_file)

        # 寫入 CSV (不處理 groups_file)
        df_questions.to_csv(questions_file, mode='a', header=write_header_q, index=False, encoding="utf-8-sig")
        
        total_generated += (len(df_questions))
        print(f"✅ 成功寫入 CSV！考點：【{current_grammar}】。累積已生成: {total_generated} 題")
        
        recent_history.append(current_scenario)
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(current_scenario + "\n")
            
        time.sleep(8) # 暫停時間微調

    except APIError as e:
        error_msg = e.message.lower()
        if "high demand" in error_msg or "503" in str(e.code) or "unavailable" in error_msg:
            print(f"⏳ 警告：Google 伺服器目前大塞車！(錯誤: {e.message})")
            time.sleep(60)
            continue 
        else:
            print(f"❌ 警告：這把 API Key 額度已耗盡或發生錯誤！\n詳細訊息: {e.message}")
            current_key_index += 1
            if current_key_index < len(API_KEYS):
                print(f"🔄 正在切換到第 {current_key_index + 1} 把 Key...")
                client = genai.Client(api_key=API_KEYS[current_key_index])
                time.sleep(5) 
            else:
                print("🛑 所有 API Key 都已嘗試完畢！程式自動停止。")
                break
            
    except Exception as e:
        print(f"⚠️ 發生未預期的錯誤: {e}")
        time.sleep(10)

print(f"\n🎉 執行完畢！本次總共為題庫貢獻了 {total_generated} 題！")