import httpx
import os
from dotenv import load_dotenv
import time

load_dotenv()

# 配置
API_BASE_URL = "http://localhost:8000"
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")
EMAIL = os.getenv("TEST_USER1_EMAIL")
PASSWORD = os.getenv("TEST_USER1_PASSWORD")

def get_token():
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_PUBLISHABLE_KEY,
        "Content-Type": "application/json"
    }
    data = {"email": EMAIL, "password": PASSWORD}
    resp = httpx.post(url, headers=headers, json=data)
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        return None
    return resp.json().get("access_token")

def test_record_flow():
    token = get_token()
    if not token:
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    print("--- 1. Testing Exam Submission ---")
    # 使用資料庫中實際存在的 question_id (根據 MCP 查詢結果)
    submit_data = {
        "attempt_type": "custom_practice",
        "config": {"parts": [5], "topic": "grammar"},
        "total_time_spent": 300,
        "answers": [
            {"question_id": "SQ_e895fe", "user_answer": "A", "time_spent": 30},
            {"question_id": "SQ_e51a2c", "user_answer": "B", "time_spent": 20}
        ]
    }
    
    resp = httpx.post(f"{API_BASE_URL}/api/v1/exams/submit", headers=headers, json=submit_data)
    if resp.status_code == 200:
        result = resp.json()
        print(f"Submission Success! Attempt ID: {result.get('attempt_id')}")
        print(f"Accuracy: {result.get('accuracy_rate') * 100}%")
    else:
        print(f"Submission Failed: {resp.text}")
        return

    print("\n--- 2. Testing History Retrieval ---")
    resp = httpx.get(f"{API_BASE_URL}/api/v1/exams/history", headers=headers, params={"limit": 5})
    if resp.status_code == 200:
        history = resp.json()
        print(f"Found {len(history)} recent attempts.")
        for h in history:
            print(f"- Type: {h['attempt_type']}, Date: {h['created_at']}")
    else:
        print(f"History Failed: {resp.text}")

    print("\n--- 3. Testing Error Book ---")
    resp = httpx.get(f"{API_BASE_URL}/api/v1/exams/errors", headers=headers, params={"status": "needs_review"})
    if resp.status_code == 200:
        errors = resp.json()
        print(f"Found {len(errors)} items in error book.")
        if errors:
            first_error_id = errors[0]['id']
            print(f"First error detail: {errors[0]['questions']['question_text'][:50]}...")
            
            print("\n--- 4. Testing Status Update ---")
            update_data = {"review_status": "mastered"}
            patch_resp = httpx.patch(f"{API_BASE_URL}/api/v1/exams/errors/{first_error_id}", headers=headers, json=update_data)
            if patch_resp.status_code == 200:
                print("Successfully marked as mastered!")
            else:
                print(f"Update Failed: {patch_resp.text}")
    else:
        print(f"Error Book Failed: {resp.text}")

if __name__ == "__main__":
    print("Starting API Verification Flow...\n")
    test_record_flow()
