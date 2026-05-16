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
    
    print("--- 1. Testing Quiz Session Flow ---")
    # Start Quiz to get a session
    start_resp = httpx.get(f"{API_BASE_URL}/api/quiz/start?count=2")
    if start_resp.status_code != 200:
        print(f"Start Quiz Failed: {start_resp.text}")
        return
    
    quiz_data = start_resp.json()
    session_id = quiz_data["session_id"]
    questions = quiz_data["questions"]
    print(f"Started Quiz! Session ID: {session_id}, Questions: {len(questions)}")

    # Prepare submission
    answers = {}
    time_spent = {}
    for q in questions:
        answers[q["id"]] = 0 # Assume option A (index 0)
        time_spent[q["id"]] = 10
    
    submit_payload = {
        "session_id": session_id,
        "answers": answers,
        "time_spent_per_q": time_spent,
        "attempt_type": "custom_practice"
    }
    
    print("\n--- 2. Testing Quiz Submission ---")
    resp = httpx.post(f"{API_BASE_URL}/api/quiz/submit", headers=headers, json=submit_payload)
    if resp.status_code == 200:
        result = resp.json()
        print(f"Submission Success! Score: {result.get('score')}")
        print(f"Correct: {result.get('correct_count')}/{len(questions)}")
    else:
        print(f"Submission Failed: {resp.text}")
        return

    print("\n--- 3. Testing History Retrieval ---")
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
