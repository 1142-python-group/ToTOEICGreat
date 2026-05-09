from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
import os
from dotenv import load_dotenv

load_dotenv()
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")
JWKS_URL = os.getenv("JWKS_URL")

app = FastAPI()
security = HTTPBearer()

jwks_client = PyJWKClient(
    JWKS_URL,
    headers={"apikey": SUPABASE_PUBLISHABLE_KEY}  # <-- 解決 401 的關鍵點
)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        # 1. 根據 Token 裡面的 kid (Key ID)，自動去 JWKS 尋找對應的公鑰
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # 2. 使用取得的公鑰解碼 Token (同時支援新的 ES256 與舊的 HS256)
        payload = jwt.decode(
            token, 
            signing_key.key, 
            algorithms=["ES256", "RS256", "HS256"], 
            audience="authenticated"
        )
        
        # 3. 回傳使用者的 UUID
        return payload.get("sub")
        
    except jwt.PyJWKClientError as e:
        raise HTTPException(status_code=500, detail=f"無法取得 Supabase 公鑰: {str(e)}")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已過期，請重新登入")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token 驗證失敗: {str(e)}")

@app.get("/me")
async def get_my_profile(user_uuid: str = Depends(verify_token)):
    return {
        "message": "驗證成功！你的架構已經升級到最新的非對稱加密標準。",
        "user_uuid": user_uuid
    }