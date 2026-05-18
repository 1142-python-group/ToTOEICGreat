import os
import json
import time
import pandas as pd
import csv
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# 載入環境變數
load_dotenv()
env_key = os.getenv("GEMINI_API_KEY_2") 
if not env_key:
    env_key = "YOUR_API_KEY_HERE"

client = genai.Client(api_key=env_key)

# ==========================================
# 1. 設定檔與 Pydantic 結構
# ==========================================
HISTORY_FILE = "judge_history.txt"
INPUT_CSV = "questions.csv"
ARTICLE_CSV = "articles.csv"  # 新增：讀取文章資料庫
OUTPUT_CSV = "suspicious_questions.csv"

class JudgeResponse(BaseModel):
    judge_answer: str = Field(description="必須是 A, B, C, 或 D")
    reason: str = Field(description="簡短說明為什麼選這個答案，以及其他選項為何不合理")

# ==========================================
# 2. 審查主邏輯
# ==========================================
def run_llm_judge():
    if not os.path.exists(INPUT_CSV):
        print(f"❌ 找不到檔案 {INPUT_CSV}，請先生成題目！")
        return

    # 讀取已檢查的歷史紀錄
    checked_ids = set()
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            checked_ids = set(f.read().splitlines())
    
    # 讀取題目
    df_questions = pd.read_csv(INPUT_CSV)
    
    # 🌟 新增：讀取文章並建立 Dictionary 供快速查詢
    article_dict = {}
    if os.path.exists(ARTICLE_CSV):
        df_articles = pd.read_csv(ARTICLE_CSV)
        # 把 group_id 當作 Key，article_text 當作 Value 存起來
        # 只要給定 group_id，就能一秒查到對應的文章內容
        article_dict = df_articles.set_index('group_id')['article_text'].to_dict()
    else:
        print(f"⚠️ 找不到 {ARTICLE_CSV}，若審查 Part 6/7 題目可能會有誤判。")

    print(f"🧠 已載入進度：系統記得已經檢查過 {len(checked_ids)} 題。")
    print("🚀 啟動 AI 審查官模式 (Temperature = 0.0) ...\n")
    
    total_to_check = len(df_questions) - sum(df_questions['question_id'].isin(checked_ids))
    if total_to_check == 0:
        print("🎉 目前題庫中的所有題目都已經檢查完畢了，沒有新題目！")
        return

    print(f"📌 本次預計檢查: {total_to_check} 題")
    newly_flagged_count = 0

    for index, row in df_questions.iterrows():
        q_id = str(row['question_id']).strip()
        group_id = str(row.get('group_id', '')).strip()
        part = str(row.get('part', ''))
        
        if q_id in checked_ids:
            continue

        q_text = row['question_text']
        opt_a = row['option_a']
        opt_b = row['option_b']
        opt_c = row['option_c']
        opt_d = row['option_d']
        original_ans = str(row['correct_answer']).strip().upper()
        
        # 🌟 關鍵邏輯：動態組合 Prompt
        # 如果這題有 group_id 且能在 article_dict 找到文章 (Part 6 / Part 7)
        # 就把文章塞進 Prompt 裡；如果找不到 (像是 Part 5)，就不塞文章。
        article_text = article_dict.get(group_id, "")
        
        context_section = ""
        if article_text:
            context_section = f"\n【請參考以下文章內容來解題】：\n{article_text}\n"

        prompt = f"""
        你是一位極度嚴格的多益考試閱卷官。請閱讀以下題目並選出「唯一正確」的解答。
        如果發現有兩個選項都可以，請選出語法與商業語境最完美的那一個。
        {context_section}
        【題目】: {q_text}
        (A) {opt_a}
        (B) {opt_b}
        (C) {opt_c}
        (D) {opt_d}
        
        請嚴格依照 JSON 格式回傳你的判斷。
        """
        
        try:
            response = client.models.generate_content(
                model='gemini-3.1-flash-lite-preview',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=JudgeResponse,
                    temperature=0.0, 
                )
            )
            
            clean_text = response.text.strip()
            md_prefix = "`" * 3 + "json"
            md_suffix = "`" * 3
            if clean_text.startswith(md_prefix): clean_text = clean_text[len(md_prefix):]
            elif clean_text.startswith(md_suffix): clean_text = clean_text[3:]
            if clean_text.endswith(md_suffix): clean_text = clean_text[:-3]
                
            result = json.loads(clean_text.strip())
            
            judge_ans = result.get('judge_answer', '').strip().upper()
            judge_reason = result.get('reason', '')
            
            if judge_ans != original_ans:
                print(f"🚩 [抓到爭議題] ID: {q_id} (Part {part}) | 原: {original_ans} | 裁判: {judge_ans}")
                
                row_dict = row.to_dict()
                row_dict['judge_answer'] = judge_ans
                row_dict['judge_reason'] = judge_reason
                
                suspicious_df = pd.DataFrame([row_dict])
                write_header = not os.path.exists(OUTPUT_CSV)
                
                suspicious_df.to_csv(
                    OUTPUT_CSV, 
                    mode='a', 
                    header=write_header, 
                    index=False, 
                    encoding='utf-8-sig',
                    quoting=csv.QUOTE_ALL
                )
                newly_flagged_count += 1
            else:
                print(f"✅ [完美通過] ID: {q_id} (Part {part})")
                
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(q_id + "\n")
            checked_ids.add(q_id)
            
        except Exception as e:
            print(f"⚠️ 審查 {q_id} 時發生錯誤: {e}，這題不會列入已檢查紀錄。")
            
        time.sleep(2) 
        
    if newly_flagged_count > 0:
        print(f"\n🚨 審查完畢！本次檢查共抓出 {newly_flagged_count} 題有爭議。")
        print(f"👉 請打開 {OUTPUT_CSV} 人工確認！")
    else:
        print(f"\n🎉 審查完畢！本次檢查的題目全部一致通過 AI 嚴格檢驗！")

if __name__ == "__main__":
    run_llm_judge()