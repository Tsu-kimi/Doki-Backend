from typing import Any, Dict
import os
from app.core.secrets import get_secret_value


def get_google_client_id() -> str:
    name = os.getenv("GOOGLE_CLIENT_ID_NAME")
    if not name:
        raise RuntimeError("GOOGLE_CLIENT_ID_NAME is not set")
    return get_secret_value(name)


def get_google_client_secret() -> str:
    name = os.getenv("GOOGLE_CLIENT_SECRET_NAME")
    if not name:
        raise RuntimeError("GOOGLE_CLIENT_SECRET_NAME is not set")
    return get_secret_value(name)


def get_google_oauth_config() -> Dict[str, str]:
    return {
        "client_id": get_google_client_id(),
        "client_secret": get_google_client_secret(),
        "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", ""),
    }


async def get_current_user() -> Dict[str, Any]:
    return {"user_id": "stub"}
