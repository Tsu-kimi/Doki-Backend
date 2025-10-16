import os
from supabase import create_client, Client
from app.core.secrets import get_secret_value


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL is not set")
    key_name = os.getenv("SUPABASE_SERVICE_ROLE_NAME")
    if not key_name:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_NAME is not set")
    key = get_secret_value(key_name)
    return create_client(url, key)
