import httpx
import asyncio
import json

# --- 配置區 ---
BASE_URL = "http://localhost:8000"

# 模擬 User A 與 User B 的 JWT (請替換為您從 Supabase 取得的真實測試 Token)
# 您可以從 Supabase Dashboard -> Auth -> Users 手動建立兩個使用者，
# 並使用他們的 Token 進行測試。
USER_A_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjNhMGVhZmRkLTFhMGItNGE4OC05MGEyLTg0MTJkMjQ2YzkyZiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL3hobHdzbmZsa3JrZnB3ZW9samdqLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiJkMWZhMjJhMy1lZWI3LTRjNTktODg2ZS0wOTJhY2ZiZTNiZDYiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzc3ODM3MjEwLCJpYXQiOjE3Nzc4MzM2MTAsImVtYWlsIjoidGVzdEBlbWFpbC5jb20iLCJwaG9uZSI6IiIsImFwcF9tZXRhZGF0YSI6eyJwcm92aWRlciI6ImVtYWlsIiwicHJvdmlkZXJzIjpbImVtYWlsIl19LCJ1c2VyX21ldGFkYXRhIjp7ImVtYWlsX3ZlcmlmaWVkIjp0cnVlfSwicm9sZSI6ImF1dGhlbnRpY2F0ZWQiLCJhYWwiOiJhYWwxIiwiYW1yIjpbeyJtZXRob2QiOiJwYXNzd29yZCIsInRpbWVzdGFtcCI6MTc3NzgzMzYxMH1dLCJzZXNzaW9uX2lkIjoiYTE5ZDkwMWItODdmOS00MDkwLTk5YjctZDcxYzlmNzA1ZjM5IiwiaXNfYW5vbnltb3VzIjpmYWxzZX0.kQW8LyhCHcpsjSGEw1Xy6ZmjO4Bs1otPw2kRjJfdTM1TwLfu6Fwdv1CIWXFZj9LgYT4FbUTZ6S1RAHh7f7D32A"
USER_B_TOKEN = "eyJhbGciOiJFUzI1NiIsImtpZCI6IjNhMGVhZmRkLTFhMGItNGE4OC05MGEyLTg0MTJkMjQ2YzkyZiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL3hobHdzbmZsa3JrZnB3ZW9samdqLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiJhN2JjNjBmYS02MTE5LTQxNzItYWNlZS00OTc3MTI1MmU1NTMiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzc3ODM3MjY1LCJpYXQiOjE3Nzc4MzM2NjUsImVtYWlsIjoidGVzdDJAZW1haWwuY29tIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJlbWFpbCIsInByb3ZpZGVycyI6WyJlbWFpbCJdfSwidXNlcl9tZXRhZGF0YSI6eyJlbWFpbF92ZXJpZmllZCI6dHJ1ZX0sInJvbGUiOiJhdXRoZW50aWNhdGVkIiwiYWFsIjoiYWFsMSIsImFtciI6W3sibWV0aG9kIjoicGFzc3dvcmQiLCJ0aW1lc3RhbXAiOjE3Nzc4MzM2NjV9XSwic2Vzc2lvbl9pZCI6ImE4NGI5M2U3LThkNDMtNDA1OS1iOGI3LWJiNWViODExNzNlNyIsImlzX2Fub255bW91cyI6ZmFsc2V9.6OZJ_DHvnOlxfPOIYWi6_hvTBIRlpenI9mLgIqup4JamyK1U3JTWuUqtLsb4Y_fuUFBXTCytCmTWRxaxe5Po0Q"
USER_B_UUID = "a7bc60fa-6119-4172-acee-49771252e553" # User B 的 ID

async def test_friendship_flow():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # 1. 驗證 User A 身份
        print("--- Step 1: Verify User A ---")
        headers_a = {"Authorization": f"Bearer {USER_A_TOKEN}"}
        me_a = await client.get("/me", headers=headers_a)
        print(f"User A UUID: {me_a.json().get('user_uuid')}")

        # 2. User A 發送好友邀請給 User B
        print("\n--- Step 2: A sends request to B ---")
        req_body = {"target_user_id": USER_B_UUID}
        res_req = await client.post("/api/v1/friends/requests", json=req_body, headers=headers_a)
        print(f"Response: {res_req.status_code}, {res_req.json()}")
        
        if res_req.status_code == 201:
            friendship_id = res_req.json().get("friendship_id")
            
            # 3. User B 查詢邀請列表
            print("\n--- Step 3: B checks pending requests ---")
            headers_b = {"Authorization": f"Bearer {USER_B_TOKEN}"}
            res_list_b = await client.get("/api/v1/friends?status=pending", headers=headers_b)
            print(f"User B Pending List: {res_list_b.json()}")

            # 4. User B 接受邀請
            print(f"\n--- Step 4: B accepts request {friendship_id} ---")
            action_body = {"action": "accept"}
            res_accept = await client.patch(f"/api/v1/friends/requests/{friendship_id}", json=action_body, headers=headers_b)
            print(f"Response: {res_accept.status_code}, {res_accept.json()}")

            # 5. User A 查詢好友列表 (應出現 User B)
            print("\n--- Step 5: A checks friend list ---")
            res_final_a = await client.get("/api/v1/friends?status=accepted", headers=headers_a)
            print(f"User A Friends: {json.dumps(res_final_a.json(), indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    if USER_A_TOKEN == "YOUR_USER_A_JWT_HERE":
        print("請先在腳本中填入有效的 USER_A_TOKEN, USER_B_TOKEN 與 USER_B_UUID 再執行測試。")
    else:
        asyncio.run(test_friendship_flow())
