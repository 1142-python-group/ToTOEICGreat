# System Design Document: 多益平台好友系統 (Friendship System)

## 1. 簡介 (Introduction)

### 1.1 目的

本文件旨在定義多益測驗平台中「好友系統」的系統架構、資料庫綱要、API 規格與安全規範。該系統允許使用者互相發送好友邀請、建立社交連結，並作為後續「好友排行榜」與「錯題/成績分享」功能的基礎建設。

### 1.2 系統範圍

- **包含：** 好友邀請的發送/接受/拒絕、好友列表查詢、解除好友關係。
- **不包含 (未來擴展)：** 即時聊天 (Real-time Chat)、動態消息 (News Feed)、封鎖系統 (Blocking System)。

---

## 2. 系統架構 (System Architecture)

本模組採用前後端分離架構，結合去中心化驗證與資料庫級別的安全控管。
本系統依賴 Auth 模組提供的 /me 解析出來的 UUID 作為操作基準。

- **Client (Next.js):** 負責發送 API 請求與狀態渲染，將 Supabase 發放的 JWT 置於 `Authorization: Bearer <token>` Header 中。
- **API Gateway (Supabase Kong):** 第一層防護，驗證 `Publishable Key` 並阻擋未授權的網路流量。
- **Backend (FastAPI):** 業務邏輯核心，透過 `JWKS` 進行 Token 解碼與身分驗證，調用 Supabase SDK 執行資料庫操作。
- **Database (PostgreSQL via Supabase):** 資料持久層，透過 Row Level Security (RLS) 確保越權存取在資料庫層級被物理阻斷。

---

## 3. 資料庫設計 (Database Schema)

### 3.1 關聯表 (Tables)

好友關係本質上是「有向圖 (Directed Graph)」轉換為「無向圖 (Undirected Graph)」的過程。我們採用單一表 `friendships` 搭配 `status` 欄位來紀錄關係。

#### Table: `friendships`

| 欄位名稱 | 型別 | 限制條件 (Constraints) | 說明 |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY, DEFAULT gen_random_uuid()` | 關係的唯一識別碼 |
| `requester_id` | `UUID` | `NOT NULL, REFERENCES public.users(id)` | 發送邀請者的 ID |
| `addressee_id` | `UUID` | `NOT NULL, REFERENCES public.users(id)` | 接收邀請者的 ID |
| `status` | `VARCHAR(20)` | `NOT NULL, DEFAULT 'pending'` | 狀態：`pending`, `accepted` |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT now()` | 紀錄建立時間 |
| `updated_at` | `TIMESTAMPTZ` | `DEFAULT now()` | 狀態最後更新時間 |

### 3.2 約束與索引 (Constraints & Indexes)

為了確保資料一致性與查詢效能，必須在資料庫層級加上以下限制：

1. **防止自我邀請 (Check Constraint):**

    ```sql
    ALTER TABLE friendships ADD CONSTRAINT check_not_self CHECK (requester_id != addressee_id);
    ```

2. **防止重複發送 (Unique Index):**

    確保 A 與 B 之間永遠只有一筆關係紀錄（無論誰發送）。

    ```sql
    CREATE UNIQUE INDEX unique_friendship_idx ON friendships (
      LEAST(requester_id, addressee_id),
      GREATEST(requester_id, addressee_id)
    );
    ```

3. **查詢效能優化 (B-tree Indexes):**

    針對頻繁的過濾欄位建立索引。

    ```sql
    CREATE INDEX idx_friendships_requester_id ON friendships(requester_id);
    CREATE INDEX idx_friendships_addressee_id ON friendships(addressee_id);
    ```

4. **狀態驗證 (Check Constraint):**

    ```sql
    ALTER TABLE friendships ADD CONSTRAINT check_status_enum CHECK (status IN ('pending', 'accepted'));
    ```

    *(註：拒絕或刪除好友時，建議直接 `DELETE` 該筆紀錄以節省空間，故不加入 'rejected' 狀態。)*

### 3.3 權限控制 (Row Level Security - RLS)

啟用 RLS 後，FastAPI 寫入資料時若帶有 user context，將受以下規則保護：

- **SELECT:** 只能看到 `requester_id` 或 `addressee_id` 為自己 UUID 的紀錄。
- **INSERT:** 只能新增 `requester_id` 為自己 UUID 的紀錄（不能偽造他人發送邀請）。
- **UPDATE:** 只有接收者 (`addressee_id`) 才能將狀態更新為 `accepted`，且當前使用者必須是接收者。
- **DELETE:** 只要是關係中的任一方（`requester_id` 或 `addressee_id` 為自己），皆可刪除紀錄（撤回邀請或解除好友）。

---

## 4. 基礎設施依賴 (Infrastructure Dependency)

### 4.1 使用者資料同步 (Auth Sync)

本系統引用 `public.users(id)`。必須確保 Supabase `auth.users` 與 `public.users` 之間已建立同步 Trigger：

- **Trigger:** 當 `auth.users` 有新紀錄時，自動 `INSERT` 到 `public.users`。
- **一致性:** 確保 `friendships` 的外鍵關聯不會失效。

---

## 4. 狀態機與業務邏輯 (State Machine)

好友關係的生命週期如下：

1. **None $\rightarrow$ Pending:** User A 發送邀請給 User B。系統 `INSERT` 一筆紀錄，狀態為 `pending`。
2. **Pending $\rightarrow$ Accepted:** User B 接受邀請。系統 `UPDATE` 該筆紀錄狀態為 `accepted`。
3. **Pending $\rightarrow$ None:** User B 拒絕邀請，或 User A 收回邀請。系統 `DELETE` 該筆紀錄。
4. **Accepted $\rightarrow$ None:** 任一方解除好友關係。系統 `DELETE` 該筆紀錄。

---

## 5. API 規格 (API Specifications)

所有 API 均需通過 FastAPI 的 JWT `verify_token` 依賴驗證。

### 5.1 發送好友邀請

- **Endpoint:** `POST /api/v1/friends/requests`
- **Request Body:**

    ```json
    {
      "target_user_id": "uuid-string"
    }
    ```

- **Logic:**
    1. 檢查 `target_user_id` 是否存在於 `users` 表。
    2. 捕捉 Unique Constraint 錯誤（若已存在 `pending` 或 `accepted` 關係，回傳 `409 Conflict`）。
    3. 寫入 `friendships`，狀態預設 `pending`。
- **Response (201 Created):**

    ```json
    { "message": "Friend request sent successfully", "friendship_id": "uuid-string" }
    ```

### 5.2 處理好友邀請 (接受/拒絕)

- **Endpoint:** `PATCH /api/v1/friends/requests/{friendship_id}`
- **Request Body:**

    ```json
    {
      "action": "accept" // 或 "reject"
    }
    ```

- **Logic:**
    1. 驗證該 `friendship_id` 存在且 `addressee_id` 為當前使用者（不能代替別人接受邀請）。
    2. 若 action 為 `accept`，UPDATE 狀態為 `accepted`。
    3. 若 action 為 `reject`，直接 DELETE 該紀錄。
- **Response (200 OK):**

    ```json
    { "message": "Request accepted" }
    ```

### 5.3 取得好友列表

- **Endpoint:** `GET /api/v1/friends`
- **Query Parameters:**
  - `status` (optional): `pending`, `accepted`。若未提供則預設回傳 `accepted`。
  - `type` (optional): 若 `status=pending` 時，可指定 `sent` (我發送的) 或 `received` (我收到的)。
- **Logic:**
  - 查詢 `friendships` 表，過濾對應狀態與當前使用者的 ID。
  - 使用 SQL `JOIN` 結合 `public.users` 表，帶出好友的 `username` 與 `email` 供前端顯示。
- **Response (200 OK):**

    ```json
    {
      "data": [
        {
          "friendship_id": "uuid-string",
          "friend_user_id": "uuid-string",
          "friend_username": "Bo-yu",
          "created_at": "2026-05-04T12:00:00Z"
        }
      ]
    }
    ```

### 5.4 解除好友關係

- **Endpoint:** `DELETE /api/v1/friends/{friend_user_id}`
- **Logic:**
    1. 尋找包含當前使用者 ID 與 `friend_user_id`，且狀態為 `accepted` 的紀錄。
    2. 執行 DELETE。
- **Response (204 No Content)**

### 5.5 收回好友邀請

- **Endpoint**: `DELETE /api/v1/friends/requests/sent/{target_user_id}`
- **Logic**:
  1. 尋找 `requester_id` 為自己，且 `addressee_id` 為 `target_user_id`，狀態為 `pending` 的紀錄。
  2. 執行 DELETE 刪除該筆紀錄。
- **Response (204 No Content)**

---

## 6. 效能與安全性考量 (Security & Performance)

1. **資料分頁 (Pagination):**
    若系統擴充至數千人，`GET /friends` 必須實作 Cursor-based Pagination，避免一次拉取過多資料導致 API Timeout 或記憶體溢出。
2. **Rate Limiting (請求限流):**
    針對 `POST /friends/requests` 實作限流（例如：每分鐘最多發送 10 次邀請），防止惡意腳本發動 DDoS 或騷擾其他使用者。
3. **N+1 Query 問題防範:**
    在取得好友列表時，FastAPI 必須使用 Supabase 支援的資源嵌入（Resource Embedding / Join），嚴禁先拉出 `friendships` 列表，再用 for 迴圈逐一打資料庫查詢 `users` 資料。

---

## 7. 未來擴展計畫 (Future Enhancements)

- **Notification System (通知系統):**
    結合 Supabase Realtime 與 PostgreSQL Triggers。當 `friendships` 表有新的 `INSERT` 時，自動推播 WebSocket 事件，讓接收者的 Next.js 前端即時顯示紅點通知。
- **Blocking System (封鎖機制):**
    未來若需實作封鎖，可在 `friendships` 中新增狀態 `blocked`，並將 Unique Index 與 RLS 邏輯相應升級，確保被封鎖者無法再發送任何邀請或查閱成績。
