# System Design Document: 好友排行榜系統 (Friend Leaderboard System)

## 1. 簡介 (Introduction)

### 1.1 目的
本文件定義多益測驗平台中「好友排行榜系統」的架構。該系統旨在透過遊戲化 (Gamification) 的機制，激發使用者的學習動機。系統將根據使用者的測驗成績與刷題數量，結合好友關係網路，動態生成多維度的排行榜。

### 1.2 系統範圍
- **包含：** 
    - **最高分榜 (Top Score Leaderboard):** 依據 `full_mock` (完整模考) 的最高分進行排名。
    - **勤勉榜 / 刷題王 (Diligence Leaderboard):** 依據指定時間內（如本週）完成的 `total_questions` 總數排名。
    - 名次計算邏輯（處理同分並列的情況，採用 `RANK()`）。
- **不包含：** 全站總排名（為避免打擊新手自信心，初期僅實作「好友圈」內的排名）。

---

## 2. 系統架構與依賴 (Architecture & Dependencies)

本模組為純粹的 **讀取密集型 (Read-Heavy)** 服務，它依賴以下兩個已存在的模組資料：
1.  **好友模組 (`friendships`):** 獲取當前使用者狀態為 `accepted` 的好友 UUID 列表。
2.  **測驗追蹤模組 (`exam_attempts`):** 獲取好友們的 `total_score` 與 `total_questions` 等統計快取數據。

---

## 3. 核心查詢邏輯與視圖設計 (Core Query Logic)

由於排行榜的查詢涉及複雜的 `JOIN` 與 `GROUP BY`，為了效能與維護性，建議在資料庫層級實作。

### 3.1 好友名單擴展 (Friend Circle Resolution)
要計算排名，受眾包含「使用者本人」+「使用者的所有好友」。
優化後的 SQL 使用 `OR` 與 `CASE` 減少掃描次數：
```sql
-- 取得 User A 的好友圈 (包含自己)
SELECT CASE 
         WHEN requester_id = 'User_A_UUID' THEN addressee_id 
         ELSE requester_id 
       END AS user_id
FROM friendships 
WHERE (requester_id = 'User_A_UUID' OR addressee_id = 'User_A_UUID') 
  AND status = 'accepted'
UNION ALL
SELECT 'User_A_UUID';
```

### 3.2 排名算法 (Ranking Algorithm)
當有兩人分數相同時，應採用標準的競賽排名算法 (`RANK()`)。
- 例如：A 得 900 分，B 得 900 分，C 得 850 分。
- 排名結果應為：A (1), B (1), C (3)。
這可以透過 PostgreSQL 內建的 Window Function `RANK() OVER (ORDER BY ... DESC)` 來完美實作。

---

## 4. API 規格 (API Specifications)

排行榜 API 統一透過 `Service Role Key` 繞過 RLS，由後端 FastAPI 全權負責組裝資料與權限過濾。

### 4.1 取得最高分排行榜 (Top Score Board)
- **Endpoint:** `GET /api/v1/leaderboard/scores`
- **Query Parameters:** 
    - `timeframe`: `all_time` (預設), `this_month`。
- **Logic:**
    1. 透過當前使用者的 Token 解析出 `user_id`。
    2. 找出該使用者的「好友圈 UUID 集合」。
    3. 在 `exam_attempts` 中篩選 `attempt_type = 'full_mock'`，抓出好友圈內每個人在指定 timeframe 內的最高 `total_score`。
    4. 依分數降冪排序，並附加名次。
- **Response (200 OK):**
    ```json
    {
      "timeframe": "all_time",
      "data": [
        {
          "rank": 1,
          "user_id": "uuid-001",
          "username": "Bo-yu",
          "score": 950,
          "is_me": false
        },
        {
          "rank": 2,
          "user_id": "my-uuid",
          "username": "Eric",
          "score": 880,
          "is_me": true
        }
      ]
    }
    ```

### 4.2 取得勤勉刷題榜 (Diligence Board)
- **Endpoint:** `GET /api/v1/leaderboard/diligence`
- **Query Parameters:** 
    - `timeframe`: `this_week` (預設), `this_month`。
- **Logic:**
    1. 獲取好友圈 UUID 集合。
    2. 篩選本週內的 `exam_attempts` (不限 `attempt_type`)。
    3. 對每個 user 的 `total_questions` 進行 `SUM()` 加總。
    4. 依刷題總數降冪排序。

---

## 5. 效能與安全性優化 (Performance & Security)

### 5.1 查詢效能防護
1. **資料庫索引:** 
   - 針對排行榜查詢建立 **部分索引 (Partial Index)**，僅索引模考數據：
     ```sql
     CREATE INDEX idx_full_mock_scores ON exam_attempts(user_id, total_score DESC) 
     WHERE attempt_type = 'full_mock';
     ```
   - 針對時間範圍建立索引：
     ```sql
     CREATE INDEX idx_exam_attempts_timeframe ON exam_attempts(created_at, user_id);
     ```
2. **物化視圖 (Materialized Views):**
   若好友數量極多，可考慮使用 `MATERIALIZED VIEW` 定期（如每小時）重新整理排行榜數據，並透過 `REFRESH MATERIALIZED VIEW CONCURRENTLY` 確保查詢不中斷。

### 5.2 安全隔離與 RLS 最佳實踐
1. **RLS 效能:** 在定義 RLS Policy 時，務必將 `auth.uid()` 包裝在 `(SELECT auth.uid())` 中，以利用 Postgres 的快取機制，避免每一列都重新解析 JWT。
2. **視圖安全性:** 若使用資料庫視圖 (View) 供 API 查詢，建議在 Postgres 15+ 中使用 `WITH (security_invoker = true)`，確保視圖遵循底層表的 RLS 規則。
3. **隱私保護:** 系統僅允許查看好友的「彙整數據」(如最高分、總題數)，嚴禁透過排行榜 API 洩漏好友的具體測驗時間或細節內容。
