import pandas as pd
import chromadb
from google import genai

# 1. 初始化設定
API_KEY = "AIzaSyBwvdGKuvy3AvzZq1Iqg4Jc19rUTt6GABg"
client = genai.Client(api_key=API_KEY)

# 建立或讀取本地端的 ChromaDB 資料庫
chroma_client = chromadb.PersistentClient(path="./toeic_chroma_db")

# 建立一個 Collection (如果之前建過了，這步會直接讀取覆蓋)
collection = chroma_client.get_or_create_collection(name="real_toeic_collection")

# 2. 讀取真實題庫資料
print("正在讀取 real_toeic.csv ...")
df = pd.read_csv("real_toeic.csv", encoding="utf-8-sig")

# 【防呆機制】將所有空值(NaN)替換為空字串，防止 ChromaDB 寫入時報錯
df = df.fillna("")

# 3. 準備寫入資料庫的容器
documents = []  # 供檢索的文字內容
metadatas = []  # 綁定的額外資訊
ids = []        # 唯一識別碼

# 4. 處理每一筆資料
for index, row in df.iterrows():
    q_id = str(row['question_id'])
    q_text = str(row['question_text'])
    tag = str(row['skill_tag'])
    
    # 將「題目」與「考點標籤」組合起來作為要轉成向量的文本
    search_text = f"考點：{tag}。題目內容：{q_text}"
    
    # 【更新區塊】將所有欄位（包含解析、翻譯與字彙）存入 Metadata
    meta = {
        "question_text": q_text,
        "options": f"(A) {row['option_a']} (B) {row['option_b']} (C) {row['option_c']} (D) {row['option_d']}",
        "correct_answer": str(row['correct_answer']),
        "skill_tag": tag,
        "explanation": str(row['explanation']),
        "translation": str(row['translation']), # 👈 新增：整句翻譯
        "vocabulary": str(row['vocabulary'])    # 👈 新增：重點字彙
    }
    
    documents.append(search_text)
    metadatas.append(meta)
    ids.append(q_id)

# 5. 呼叫 Gemini 的 Embedding 模型將文字轉為向量
print(f"正在將 {len(documents)} 筆題目轉換為向量並存入資料庫...")

embeddings = []
for doc in documents:
    response = client.models.embed_content(
        model='gemini-embedding-001',
        contents=doc
    )
    embeddings.append(response.embeddings[0].values)

# 6. 將向量、文件、Metadata 一起塞進 ChromaDB
# 使用 upsert，如果 ID 已經存在就會更新它，不會重複新增
collection.upsert(
    ids=ids,
    embeddings=embeddings,
    documents=documents,
    metadatas=metadatas
)

print("✅ 向量資料庫建置完成！現在資料庫內已包含完整的翻譯與字彙資訊。")