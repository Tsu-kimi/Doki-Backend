"""
Token encryption utilities using Fernet (symmetric encryption).
Tokens are encrypted at rest in the database for security.
"""
import os
from functools import lru_cache
from cryptography.fernet import Fernet
from app.core.secrets import get_secret_value


@lru_cache(maxsize=1)
def _get_cipher() -> Fernet:
    """Get or create Fernet cipher instance using encryption key from Secret Manager."""
    key_name = os.getenv("ENCRYPTION_KEY_NAME")
    if not key_name:
        raise RuntimeError("ENCRYPTION_KEY_NAME is not set in environment")
    key = get_secret_value(key_name)
    return Fernet(key.encode())


def encrypt_token(plaintext: str) -> bytes:
    """
    Encrypt a plaintext token for storage.
    
    Args:
        plaintext: The token string to encrypt
        
    Returns:
        Encrypted bytes suitable for storage in bytea column
    """
    if not plaintext:
        return b""
    cipher = _get_cipher()
    return cipher.encrypt(plaintext.encode())


def decrypt_token(encrypted: bytes) -> str:
    """
    Decrypt a token from storage.
    
    Args:
        encrypted: The encrypted bytes from database
        
    Returns:
        Decrypted plaintext token string
    """
    if not encrypted:
        return ""
    cipher = _get_cipher()
    return cipher.decrypt(encrypted).decode()


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.
    Use this to create ENCRYPTION_KEY for your environment.
    
    Returns:
        Base64-encoded encryption key string
    """
    return Fernet.generate_key().decode()
