import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

# 1. 載入 .env 檔案裡的環境變數
load_dotenv()

# 2. 取得 Supabase 的網址與金鑰
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("❌ 錯誤：找不到 Supabase URL 或 Key，請檢查 .env 檔案！")
    exit()

# 3. 建立 Supabase 連線客戶端
supabase: Client = create_client(url, key)

# 4. 讀取你辛苦生成的 CSV 題庫
csv_file = "questions.csv"
try:
    # ✅ 進化寫法：自動處理編碼衝突
    try:
        df = pd.read_csv(csv_file, encoding='utf-8-sig', on_bad_lines='skip')
    except UnicodeDecodeError:
        df = pd.read_csv(csv_file, encoding='cp950', on_bad_lines='skip')
    print(f"📊 成功讀取 CSV，準備上傳 {len(df)} 題...")
    
    # 先強制轉成 object 允許塞入 None，再進行替換
    df = df.astype(object).where(pd.notnull(df), None)
    
    # 將 DataFrame 轉換為字典列表 (List of Dictionaries)
    records = df.to_dict(orient='records')
    
    # 5. 寫入 Supabase 資料庫
    # ⚠️ 注意：這裡假設隊友在 Supabase 裡建好的資料表名稱叫做 'questions'
    # 如果隊友建的名字不一樣（例如叫 'toeic_questions'），請把下面這行的 'questions' 改掉
    response = supabase.table('questions').upsert(records).execute()
    
    print("✅ 太神啦！資料已經全數成功寫入 Supabase 雲端資料庫！")
    print("你可以請隊長去後台看，或是直接用前端測試了！")

except Exception as e:
    print(f"❌ 上傳過程中發生錯誤：{e}")