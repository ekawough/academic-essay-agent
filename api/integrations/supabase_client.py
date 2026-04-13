import os
from supabase import create_client, Client

def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
    return create_client(url, key)

supabase: Client = None

def init_supabase():
    global supabase
    try:
        supabase = get_supabase()
        print("Supabase connected.")
    except Exception as e:
        print(f"Supabase not configured: {e}")
        supabase = None
