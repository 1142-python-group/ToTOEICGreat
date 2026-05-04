# System Design Document: 測驗追蹤與錯題系統 (Score & Error Tracking System)

## 1. 簡介 (Introduction)

### 1.1 目的

本文件定義多益測驗平台中「測驗追蹤與錯題系統」的架構。本系統負責處理使用者交卷邏輯、快取成績統計數據，並透過動態查詢技術提供「即時錯題本」與「弱點分析」功能。本模組不負責題庫的建置與管理，而是透過唯讀參考 (Foreign Key / Reference) 的方式，獲取並整合全域題庫的資料。

### 1.2 系統範圍

- **包含：** 測驗結果批次寫入 (Bulk Insert)、動態錯題本生成、錯題複習狀態追蹤、成績歷史與正確率統計。
- **不包含：**
  - **題庫內容管理 (Question Content Management)：** 多益題庫的增刪改查由獨立的題庫模組負責，本系統僅具備讀取與關聯權限。
  - 測驗過程防作弊機制。
  - 考卷生成的亂數抽題演算法。

---

## 2. 資料庫設計 (Database Schema)

本系統建立於2個核心資料表之上：`exam_attempts` (測驗統計)、`answer_records` (作答明細)。

本系統高度依賴 `questions` 資料表。

- **唯讀存取:** 本模組在資料庫層級（或 API 層級）僅對 `questions` 表擁有 `SELECT` 權限。
- **資料一致性:** 當外部模組對 `questions` 進行刪除或修改時，必須確保 `answer_records` 的 `question_id` 外鍵具備合適的串聯策略（例如設定為 `ON DELETE SET NULL`，或是採用軟刪除 `Soft Delete`），以避免破壞歷史作答明細與錯題本的完整性。

### 2.1 Table: `questions` (統一題庫)

所有題目皆儲存於此，具備單一事實來源 (Single Source of Truth) 特性，方便後續 AI 進行弱點標籤比對。

| 欄位名稱 | 型別 | 限制條件 | 說明 |
| :--- | :--- | :--- | :--- |
| `question_id` | `VARCHAR(50)` | `PRIMARY KEY` | 題目的唯一識別碼 (例: Q_P5_0001) |
| `part` | `SMALLINT` | `NOT NULL` | 多益大題分類 (1~7) |
| `group_id` | `VARCHAR(50)` | | 題組 ID (針對 Part 3, 4, 6, 7) |
| `question_text` | `TEXT` | | 題目本文或圖片 URL |
| `option_a` | `TEXT` | `NOT NULL` | 選項 A |
| `option_b` | `TEXT` | `NOT NULL` | 選項 B |
| `option_c` | `TEXT` | | 選項 C (聽力應答可能只有三個) |
| `option_d` | `TEXT` | | 選項 D |
| `correct_answer` | `VARCHAR(1)` | `NOT NULL` | 正確答案 (`A`, `B`, `C`, `D`) |
| `explanation` | `TEXT` | | 官方或 AI 產生的詳解 |
| `skill_tag` | `JSONB` | | 考點標籤 (例: `["grammar", "tense"]`) |
| `translation` | `TEXT` | | 中文翻譯 |
| `vocabulary` | `TEXT` | | 重點單字解析 |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT now()` | 建檔時間 |

### 2.2 Table: `exam_attempts` (測驗紀錄與統計快取)

作為一次作答紀錄的 Header，並快取聚合數據以大幅提升儀表板讀取效能。

| 欄位名稱 | 型別 | 限制條件 | 說明 |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | 測驗紀錄唯一碼 |
| `user_id` | `UUID` | `NOT NULL, REFERENCES public.users(id)` | 應試者 ID |
| `attempt_type` | `VARCHAR(20)` | `NOT NULL` | `full_mock` (完整模考) 或 `custom_practice` (自訂練習) |
| `config` | `JSONB` | | 紀錄測驗參數 (例如: `{"parts": [5,6], "limit": 30}`) |
| `total_questions` | `INT` | `NOT NULL` | 本次測驗總題數 |
| `correct_answers` | `INT` | `NOT NULL` | 答對題數 |
| `accuracy_rate` | `NUMERIC(5,4)` | `NOT NULL` | 正確率 (0.0000 ~ 1.0000) |
| `total_score` | `INT` | | 多益量尺總分 (僅 `full_mock` 有值，其餘為 null) |
| `listening_score` | `INT` | | 聽力量尺分數 (同上) |
| `reading_score` | `INT` | | 閱讀量尺分數 (同上) |
| `total_time_spent` | `INT` | `DEFAULT 0` | 總花費時間 (秒) |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT now()` | 交卷時間 |

### 2.3 Table: `answer_records` (作答明細 / 錯題本基底)

完整紀錄使用者的每一題作答狀態。透過過濾此表，即可動態生成錯題本。

| 欄位名稱 | 型別 | 限制條件 | 說明 |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | 明細唯一碼 |
| `attempt_id` | `UUID` | `NOT NULL, REFERENCES exam_attempts(id)` | 關聯的測驗場次 |
| `user_id` | `UUID` | `NOT NULL, REFERENCES public.users(id)` | 應試者 ID (需與 `auth.users` 同步，加速跨卷查詢) |
| `question_id` | `VARCHAR(50)` | `NOT NULL, REFERENCES questions(question_id)` | 關聯的題庫題目 |
| `user_answer` | `VARCHAR(1)` | | 使用者作答選項 (`A`, `B`, `C`, `D`，未答為 null) |
| `is_correct` | `BOOLEAN` | `NOT NULL` | 是否答對 |
| `time_spent` | `INT` | `DEFAULT 0` | 單題花費時間 (秒) |
| `review_status` | `VARCHAR(20)` | `DEFAULT NULL` | 錯題狀態：`NULL` (答對不追蹤), `needs_review` (待複習), `mastered` (已掌握) |

### 2.4 約束與索引 (Constraints & Indexes)

為了確保千萬級別別別資料量的查詢效能，必須建立以下 B-Tree 索引：

1. **測驗紀錄過濾 (加速歷史清單讀取):**

    ```sql
    CREATE INDEX idx_exam_attempts_user_id ON exam_attempts(user_id);
    CREATE INDEX idx_exam_attempts_type ON exam_attempts(user_id, attempt_type);
    ```

2. **錯題本動態生成 (極度重要，加速錯題檢索):**

    ```sql
    -- 複合索引：精準鎖定特定使用者的錯題
    CREATE INDEX idx_answer_records_errors ON answer_records(user_id, is_correct, review_status);
    ```

3. **關聯查詢優化:**

    ```sql
    CREATE INDEX idx_answer_records_attempt_id ON answer_records(attempt_id);
    ```

---

## 3. RLS 安全控制與權限隔離

為確保資料安全性，所有資料表必須啟用 Row Level Security (RLS)。

1. `questions` 表：
    - **SELECT**: `TO authenticated` (登入者皆可讀取題目)。
    - **INSERT/UPDATE/DELETE**: `TO service_role` (僅後端管理員可修改題庫)。

2. `exam_attempts` & `answer_records` 表 (嚴格權限隔離)：
    - **效能優化**: 使用 `(SELECT auth.uid())` 取代 `auth.uid()` 以利用 PostgreSQL 的快取機制，大幅提升大規模過濾時的效能。
    - **SELECT**: 僅允許讀取自己的紀錄。

      ```sql
      CREATE POLICY "Users can view own records" ON table_name 
      FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);
      ```

    - **INSERT**: 僅允許以自己的 `user_id` 寫入。

      ```sql
      CREATE POLICY "Users can insert own records" ON table_name 
      FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);
      ```

    - **UPDATE**: 僅允許修改自己的紀錄，且禁止變更 `user_id`。

      ```sql
      CREATE POLICY "Users can update own records" ON table_name 
      FOR UPDATE TO authenticated 
      USING ((SELECT auth.uid()) = user_id) 
      WITH CHECK ((SELECT auth.uid()) = user_id);
      ```

---

## 4. 核心業務邏輯 (Business Logic)

### 4.1 交卷與分數計算機制 (Transaction Context)

前端在使用者交卷時，必須傳送一包完整的 JSON (包含測驗設定與所有作答明細)。FastAPI 接收後，需執行以下步驟：

1. **核對答案**：依據 `question_id` 從快取或資料庫比對 `correct_answer`，判定每一題的 `is_correct`。
2. **統計計算**：計算 `correct_answers` 與 `accuracy_rate`。若為 `full_mock`，則呼叫內部的量尺轉換函數計算 `total_score`。
3. **狀態初始化**：針對 `is_correct = false` 的題目，將其 `review_status` 設為 `needs_review`。
4. **資料庫寫入 (Transaction)**：
    - 先 `INSERT INTO exam_attempts` 取得 `attempt_id`。
    - 利用拿到的 `attempt_id`，執行批次寫入 `INSERT INTO answer_records` (使用 `supabase.table().insert(list_of_dicts)` 進行 Bulk Insert)。

> **進階實作建議 (Security & Performance):**  
> 若未來有高度防作弊需求（防止前端篡改 `is_correct` 或分數），建議將上述 1~4 步邏輯封裝於 **Supabase Edge Function** 或 **PostgreSQL RPC (Stored Procedure)** 中。由後端直接從 `questions` 表抓取正確答案進行判定，確保計算過程的封閉性與資料完整性。

### 4.2 動態錯題本機制 (Dynamic Error Book)

無需額外的錯題庫資料表。當使用者進入錯題本介面時，API 發出以下查詢指令，結合 `questions` 表自動展開所有題目細節：

```sql
SELECT ar.*, q.question_text, q.correct_answer, q.explanation, q.skill_tag
FROM answer_records ar
JOIN questions q ON ar.question_id = q.question_id
WHERE ar.user_id = '<user_uuid>' 
  AND ar.is_correct = false 
  AND ar.review_status = 'needs_review'
ORDER BY ar.time_spent DESC; -- 優先顯示卡最久的錯題
```

---

## 5. API 規格 (API Specifications)

### 5.1 批次繳交試卷

- **Endpoint:** `POST /api/v1/exams/submit`
- **Request Body:**

    ```json
    {
      "attempt_type": "custom_practice",
      "config": { "parts": [5], "topic": "grammar" },
      "total_time_spent": 1200,
      "answers": [
        { "question_id": "Q_P5_0001", "user_answer": "A", "time_spent": 45 },
        { "question_id": "Q_P5_0002", "user_answer": "C", "time_spent": 30 }
      ]
    }
    ```

- **Response (201 Created):** 回傳聚合好的成績摘要與新建立的 `attempt_id`。

### 5.2 取得測驗歷史 (儀表板數據)

- **Endpoint:** `GET /api/v1/exams/history`
- **Query Params:** `type=full_mock` (可選，過濾測驗類型), `limit=10`。
- **Logic:** 查詢 `exam_attempts` 並依日期反序排列。

### 5.3 取得錯題本列表

- **Endpoint:** `GET /api/v1/exams/errors`
- **Query Params:** `status=needs_review` (預設), `part=5` (可選，依大題篩選)。
- **Logic:** 執行上述 4.2 的 JOIN 查詢，回傳包含題目詳解的列表。

### 5.4 更新錯題狀態 (標記為已掌握)

- **Endpoint:** `PATCH /api/v1/exams/errors/{record_id}`
- **Request Body:** `{"review_status": "mastered"}`
- **Logic:** 更新該筆 `answer_records` 的複習狀態。
