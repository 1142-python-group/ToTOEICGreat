 # ToTOEICGreat - 數位化 TOEIC 學習平台

這是一個基於 Python FastAPI 和 Vue.js 的現代化線上測驗平台，旨在提供沉浸式的多益（TOEIC）模擬測驗體驗。平台整合了 AI 助教、個人化學習分析與社群互動功能，幫助使用者有效提升英文能力。

## 🚀 系統架構總覽

本專案採用前後端分離的架構設計，清晰劃分職責，便於維護與擴展。

### 1. 後端服務 (FastAPI)
基於 Python 3.11+ 開發，提供 RESTful API 介面及安全的認證機制。

* **技術栈**:
    * **框架**: [FastAPI](https://fastapi.tiangolo.com/) (`main.py`)
    * **資料庫**: [Supabase](https://supabase.com/) (PostgreSQL)
    * **認證**: JWT Token (通過 Supabase Auth 整合)
    * **AI 整合**: [LLM API](https://github.com/Eric-1107/ToTOEICGreat/blob/main/backend/routers/ai_service/ai_assistant.py)
* **核心功能**:
    * **測驗系統**: 提供「全真模考」與「自訂練習」模式，支援隨機出題。
    * **成績分析**: 自動生成聽力與閱讀分數（基於正確題數）。
    * **進度追蹤**: 記錄錯題與挑戰題，用於後續複習。
    * **排行榜**: 支援「分數」與「勤勉度」（完成題數）兩種排行榜機制。

### 2. 前端介面 (Vue 3)
基於 Vue 3 開發的單頁應用（SPA），提供流暢的互動體驗。

* **技術栈**:
    * **框架**: Vue 3 (`frontend/`)
    * **狀態管理**: Vue 3 Reactivity API
    * **API 整合**: 原生 `fetch` 搭配 `async/await`
* **核心功能**:
    * **多頁面切換**:
        * **首頁**: 測驗功能入口與個人化數據概覽。
        * **好友系統**: 透過代碼新增好友、處理邀請，並可與好友進行排名對比。
        * **作答紀錄**: 完整的歷史紀錄列表，支援跳轉至單次測驗的「作答詳情」。
        * **排行榜**: 即時查看分數與勤勉度排行榜，支援週/月/總體時間切換。
        * **作答介面**: 整合聽力與閱讀試題的沈浸式互動介面。
    * **AI 互動與錯題管理**:
        * **錯題本詳情**: 檢視題目、選項、正確答案與 AI 解析。
        * **狀態標記**: 可將錯題標記為「需要複習」、「已複習」或「已學會」。
        * **自動出題**: 根據錯題生成相似題型（開發中）。

---

## ⚙️ 環境建置與執行教學

### 必備環境
* Python 3.8+
* 現代化瀏覽器 (支援 Vue 3)
* Supabase 帳號（用於資料儲存與認證）

### 後端設定 (FastAPI)

1.  **Clone 專案**
    ```bash
    git clone https://github.com/Eric-1107/ToTOEICGreat.git
    cd ToTOEICGreat/backend
    ```

2.  **安裝依賴**
    ```bash
    pip install fastapi uvicorn supabase python-dotenv
    ```

3.  **環境變數**
    建立 `.env` 檔案，並填入您的 Supabase 連線資訊：
    ```ini
    SUPABASE_URL=您的_SUPABASE_URL
    SUPABASE_SECRET_KEY=您的_SUPABASE_SECRET_KEY
    ```

4.  **執行後端**
    ```bash
    uvicorn main:app --reload --host [IP_ADDRESS] --port 8000
    ```

### 前端設定 (Vue 3)

1.  **進入前端目錄**
    ```bash
    cd ../frontend
    ```

2.  **啟動開發伺服器**
    ```bash
    python -m http.server 3000
    ```
    預設會開啟瀏覽器 `http://localhost:3000`

---

## 📂 專案結構說明

```
ToTOEICGreat/
├── backend/                # FastAPI 後端服務
│   ├── main.py             # API 入口與全局路由設定
│   ├── routers/            # 業務模組化路由
│   │   ├── account_service/  # 帳號認證與 JWT 驗證 (Supabase)
│   │   ├── friendship_service/ # 好友系統與邀請機制
│   │   ├── leaderboard_service/ # 排行榜 (分數/勤勉度)
│   │   ├── history_practice/ # 生成個人化考題
│   │   └── record_services/  # 作答紀錄與錯題本管理
│   ├── questions.csv       # 靜態題庫資料
│   └── .env                # 環境變數 (需自行建立)
│
└── frontend/               # 前端網頁介面 (Vue 3 CDN 版)
    ├── index.html          # 主頁面入口
    ├── app.js              # Vue 邏輯與 API 請求封裝
    ├── auth.js             # Supabase Auth 認證邏輯
    └── css/
        └── style.css       # 系統樣式表
```

---

## 🤝 貢獻指南

歡迎對本專案提出 Issues 或 Pull Requests。在提交代碼前，請確保已遵循以下規範：
1.  符合 PEP 8 程式碼風格。
2.  更新相關的 `README.md` 文件（如有必要）。
3.  前端變更應先在開發伺服器上測試無誤。
