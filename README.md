# ToTOEICGreat - 多多益善：AI 驅動的多益數位化學習平台

這是一個結合了 **FastAPI**、**Vue 3** 與 **Gemini AI** 的現代化多益（TOEIC）學習與模擬測驗平台。本專案旨在提供全方位的多益備考體驗，從 AI 生成題目、聽力語音合成，到個人化弱點分析與社群排行榜，幫助使用者精準提升英語實力。

---

## 🌟 核心特色

1.  **AI 命題與解析**：
    *   利用 **Gemini 2.5 Flash** 結合 **RAG (Retrieval-Augmented Generation)** 技術，參考真實考題生成高品質模擬題。
    *   每一道題目皆附帶 AI 生成的詳細解析、全文翻譯及重點單字。
2.  **沉浸式聽力體驗**：
    *   使用 **Edge-TTS** 模擬多國口音（美、英、澳、加），提供高品質的聽力試題音檔。
3.  **個人化弱點分析**：
    *   **雷達圖分析**：將作答紀錄分為「文法概念」、「單字運用」、「聽力理解」、「閱讀理解」四大維度。
    *   **進度追蹤**：視覺化展示歷史成績折線圖與預估多益分數。
4.  **AI 錯題練習**：
    *   系統能針對使用者的錯題，即時從題庫中檢索出相同考點的類似題，進行加強練習。
5.  **社群互動系統**：
    *   透過好友代碼建立連結，即時查看好友排行榜，互相激勵。

---

## 🏗️ 系統架構

### 1. 後端服務 (FastAPI)
*   **API 框架**：FastAPI
*   **資料庫**：Supabase (PostgreSQL)
*   **向量資料庫**：ChromaDB (用於 RAG 題目生成)
*   **AI 引擎**：Google Gemini API
*   **身分驗證**：Supabase Auth (JWT)

### 2. 前端介面 (Vue 3)
*   **核心框架**：Vue 3 (CDN 版本)
*   **圖表庫**：Chart.js (用於雷達圖與折線圖)
*   **樣式**：Vanilla CSS
*   **通訊**：原生 Fetch API

### 3. 資料處理流水線 (Pre-processing)
*   **聽力生成**：`generate_audio.py` 透過 Edge-TTS 批量轉換 CSV 腳本為 MP3。
*   **題目研發**：`ToeicLLM.py` 結合 ChromaDB 向量檢索，自動產出具備多益難度的 Part 5/6/7 試題。
*	**AI 交叉審查 (LLM-as-a-Judge)**：`llm_judge.py` 引入低溫度 (Temperature=0.0) 的裁判模型，對生成的題目進行邏輯與文法盲測，自動抓出「雙胞胎選項」或「幻覺錯題」。
*	**智慧清理機制**：`delete_bad_questions.py` 針對爭議題，透過腳本連動 `group_id`，一鍵從 Supabase 徹底清除無效題組。

---

## 📂 專案結構與模組說明

```
toToeicGreat/
├── backend/
│   ├── main.py             # 主程式：路由註冊與測驗邏輯
│   ├── database.py         # Supabase 用戶端初始化
│   ├── models.py           # Pydantic 資料模型定義
│   ├── routers/            # 模組化路由
│   │   ├── auth.py         # 用戶認證
│   │   ├── exams.py        # 測驗紀錄管理
│   │   ├── quiz.py         # 核心出題逻辑
│   │   ├── friends.py      # 好友與排行榜
│   │   └── history_practice.py # AI 弱點加強練習
│   ├── listening_questions/ # 聽力前處理
│   │   ├── generate_audio.py # TTS 語音合成
│   │   └── upload_supabase.py # 音檔與資料上傳
│   └── reading_questions/   # 閱讀前處理
│       ├── build_vectordb.py # 建置 ChromaDB
│       ├── ToeicLLM.py       # AI 命題系統 (RAG)
│       ├── upload_articles.py # 閱讀文章上傳
│ 		├── delete_supabase.py # AI 自動刪除錯題
│ 		└── llm_judge.py  # AI 審題系統
├── frontend/
│   ├── index.html          # SPA 入口頁面
│   ├── app.js              # Vue 邏輯與介面管理
│   ├── auth.js             # 登入與權限檢查
│   └── css/style.css       # 系統全局樣式
└── testing/                # 自動化測試腳本
```

---

## 📊 資料結構 (Database Schema)

*   **`users`**: 儲存使用者帳號資訊與個人設定。
*   **`questions`**: 核心題庫，包含 Part 2、Part 3、Part 5、Part 6、Part -7、題目文字、選項、正確答案、AI 解析、翻譯、單字及音檔路徑。
*   **`article`**: 儲存 Part 6 與 Part 7 的閱讀文章內容及其翻譯。
*   **`exam_attempts`**: 每次完整測驗的總結紀錄（分數、正確率、總用時）。
*   **`answer_records`**: 每道題目的詳細作答情況（使用者答案、是否正確、作答秒數）。
*   **`friendships`**: 好友關係與邀請狀態。

---

## ⚙️ 環境建置與使用方式

### 1. 環境設定
在 `backend/` 目錄下建立 `.env` 檔案：
```ini
SUPABASE_URL=your_supabase_url
SUPABASE_SECRET_KEY=your_supabase_anon_key
GEMINI_API_KEY=your_google_gemini_api_key
```

### 2. 前處理 (Data Preparation)
在使用平台前，需先填充題庫：
1.  **生成音檔**：執行 `python backend/listening_questions/generate_audio.py`。
2.  **上傳資料**：執行 `python backend/listening_questions/upload_supabase.py` 及相關閱讀題上傳腳本。
3.  **建置向量庫**：執行 `python backend/reading_questions/build_vectordb.py` 以便後續 AI 命題使用。

### 3. 啟動服務
1.  **啟動後端**：
    ```bash
    cd backend
    pip install -r requirements.txt
    uvicorn main:app --reload
    ```
2.  **啟動前端**：
    直接開啟 `frontend/index.html` 或使用靜態伺服器：
    ```bash
    cd frontend
    python -m http.server 3000
    ```

---
*本專案為「程式設計-Python」課程期末專題。*
