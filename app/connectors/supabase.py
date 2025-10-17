import os
from supabase import create_client, Client
from app.core.secrets import get_secret_value
from typing import List, Dict


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL is not set")
    key_name = os.getenv("SUPABASE_SERVICE_ROLE_NAME")
    if not key_name:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_NAME is not set")
    key = get_secret_value(key_name)
    return create_client(url, key)


def list_tables() -> List[Dict[str, object]]:
    return [
        {
            "table": "profiles",
            "columns": [
                {"name": "id", "type": "uuid"},
                {"name": "email", "type": "text"},
                {"name": "created_at", "type": "timestamp"},
            ],
        },
        {
            "table": "mapping_rules",
            "columns": [
                {"name": "id", "type": "uuid"},
                {"name": "user_id", "type": "uuid"},
                {"name": "source_field", "type": "text"},
                {"name": "target_field", "type": "text"},
            ],
        },
    ]
