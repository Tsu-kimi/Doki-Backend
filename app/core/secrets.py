import os
from functools import lru_cache
from google.cloud import secretmanager

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = secretmanager.SecretManagerServiceClient()
    return _client


def get_project_id() -> str:
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        raise RuntimeError("GCP_PROJECT_ID is not set")
    return project_id


@lru_cache(maxsize=64)
def get_secret_value(secret_name: str, version: str = "latest") -> str:
    if not secret_name:
        raise ValueError("secret_name is required")
    name = f"projects/{get_project_id()}/secrets/{secret_name}/versions/{version}"
    client = _get_client()
    response = client.access_secret_version(name=name)
    return response.payload.data.decode("utf-8")
