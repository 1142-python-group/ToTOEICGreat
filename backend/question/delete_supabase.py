import os
from dotenv import load_dotenv
from supabase import create_client, Client

# ---------------------------------------------------------
# 1. 環境變數與 Supabase 初始化
# ---------------------------------------------------------
load_dotenv()
# ⚠️ 注意：刪除資料建議使用 Service Role Key，才能繞過 RLS 安全限制
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") 

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ 找不到 Supabase 變數，請確認 .env 檔案設定。")
    exit()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------
# 2. 待刪除的「錯誤題目 ID」清單
# ---------------------------------------------------------
# 這裡放入我們剛剛確認要報廢的爛題目 ID
BAD_QUESTION_IDS = [
    "SQ_2ffd47",
    "SQ_dc572b", # 靈異現象題 (Part 5)
    "SQ_7491c1", # 雙胞胎選項 (Part 5)
    "SQ_64b029", # 模稜兩可 (Part 5)
    "SQ_adb5cf",  # 模稜兩可 (Part 5)
    "SQ_38807f",
    "SQ_5b1c24", # 靈異現象題 (Part 5)
    "SQ_adc815", # 雙胞胎選項 (Part 5)

]

# ---------------------------------------------------------
# 3. 智慧刪除邏輯
# ---------------------------------------------------------
def clean_up_database():
    print(f"🗑️ 準備執行清理，共計 {len(BAD_QUESTION_IDS)} 個標的物...\n")

    for q_id in BAD_QUESTION_IDS:
        try:
            # 第一步：先查詢這題的 part 和 group_id
            response = supabase.table("questions").select("part, group_id").eq("question_id", q_id).execute()
            
            if not response.data:
                print(f"⚠️ 略過：找不到題目 {q_id} (可能已經被刪除過了)")
                continue

            q_info = response.data[0]
            part = q_info.get("part")
            group_id = q_info.get("group_id")

            # 第二步：根據 Part 決定刪除策略
            if part in [6, 7] and group_id:
                print(f"🔍 [題組刪除] 發現 {q_id} 屬於 Part {part} (Group ID: {group_id})")
                
                # 刪除關聯的文章 (Article)
                article_del = supabase.table("article").delete().eq("group_id", group_id).execute()
                if article_del.data:
                    print("   -> 📄 已刪除關聯的 1 篇文章")
                
                # 刪除該題組底下的所有題目 (Questions)
                question_del = supabase.table("questions").delete().eq("group_id", group_id).execute()
                print(f"   -> 📝 已刪除同題組的 {len(question_del.data)} 筆題目")
                print(f"✅ 題組 {group_id} 已徹底清除！\n")
                
            else:
                print(f"🔍 [單題刪除] 發現 {q_id} 屬於 Part {part} 獨立題")
                # 獨立題目直接刪除
                supabase.table("questions").delete().eq("question_id", q_id).execute()
                print(f"✅ 題目 {q_id} 已成功刪除！\n")

        except Exception as e:
            print(f"❌ 處理 {q_id} 時發生不可預期的錯誤: {str(e)}\n")

    print("🎉 所有的錯誤題目與幽靈關聯都已經清理完畢！")

if __name__ == "__main__":
    clean_up_database()