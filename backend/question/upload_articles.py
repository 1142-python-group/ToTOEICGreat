import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

# ==========================================
# 1. 載入環境變數與連線設定
# ==========================================
load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY") # 執行寫入務必使用 Secret Key / Service Role Key

if not url or not key:
    raise RuntimeError("❌ 找不到 Supabase 憑證，請檢查 .env 檔案是否設定正確")

supabase: Client = create_client(url, key)

# ==========================================
# 2. 上傳腳本主邏輯
# ==========================================
def upload_articles(csv_filename="articles.csv", table_name="article"):
    if not os.path.exists(csv_filename):
        print(f"⚠️ 找不到檔案 {csv_filename}，請確認檔名是否正確。")
        return

    print(f"🚀 開始讀取 {csv_filename} 並準備上傳至 Supabase...")

    try:
        # 1. 讀取標準 CSV
        df = pd.read_csv(csv_filename, encoding='utf-8-sig')

        # 2. 清理欄位名稱：洗掉頭尾的空白和隱形逗號
        df.rename(columns=lambda x: str(x).strip().strip(',"'), inplace=True)
        
        # 3. 踢除 Excel 存檔容易產生的 Unnamed 幽靈欄位
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

        # [防呆檢查] 確認必要欄位是否存在
        expected_columns = ["group_id", "article_type", "article_text", "article_translation", "vocabulary"]
        missing_cols = [col for col in expected_columns if col not in df.columns]
        if missing_cols:
            print(f"⚠️ 警告: 你的 CSV 缺少了這些欄位: {missing_cols}，這可能會導致上傳失敗！")

        # 4. 確保 group_id 沒有重複 (若 CSV 內有重複，只保留最後一筆)
        df.drop_duplicates(subset=['group_id'], keep='last', inplace=True)

        # 5. 將空值轉成 None (Supabase 不吃 Pandas 的 NaN，會報錯)
        df = df.astype(object).where(pd.notnull(df), None)

        # 轉換成 JSON 字典格式
        records = df.to_dict(orient='records')
        
        if not records:
            print("⚠️ CSV 內沒有有效的資料可供上傳。")
            return
        
        print(f"📦 準備上傳 {len(records)} 筆資料...")

        # ==========================================
        # 3. 執行 Upsert 的魔法指令
        # ==========================================
        # 只要 Supabase 裡面的 Primary Key 是 group_id，
        # .upsert() 就會自動做到：「有這個 ID 就覆蓋更新，沒有這個 ID 就新增」
        response = supabase.table(table_name).upsert(records).execute()
        
        print(f"✅ 成功將 {len(records)} 筆資料 Upsert 至 {table_name} 資料表！")

    except Exception as e:
        print(f"❌ 上傳 {csv_filename} 時發生嚴重的錯誤: {e}")

# ==========================================
# 程式進入點
# ==========================================
if __name__ == "__main__":
    # 根據你實際儲存的 CSV 檔名修改第一個參數 (如 "article.csv" 或 "articles.csv")
    upload_articles(csv_filename="articles.csv", table_name="article")