import httpx
from dotenv import load_dotenv
import os

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")
TEST_EMAIL = os.getenv("TEST_EMAIL")
TEST_PASSWORD = os.getenv("TEST_PASSWORD")

# 請替換成你專案的真實資料

def get_supabase_token():
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_PUBLISHABLE_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    response = httpx.post(url, headers=headers, json=data)
    if response.status_code == 200:
        token = response.json().get("access_token")
        print(f"成功取得 Token！請將以下字串複製到 Swagger UI：\n\n{token}\n")
    else:
        print(f"登入失敗: {response.text}")

if __name__ == "__main__":
    get_supabase_token()