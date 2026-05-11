import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise RuntimeError("缺少 SUPABASE_URL 或 SUPABASE_SECRET_KEY 環境變數")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)