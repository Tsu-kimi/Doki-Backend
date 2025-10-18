"""
Token encryption utilities using Fernet (symmetric encryption).
Tokens are encrypted at rest in the database for security.
"""
import os
import base64
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


def encrypt_token_for_storage(plaintext: str) -> str:
    """
    Encrypt a token for JSON-compatible storage in bytea.
    
    Fernet tokens are already base64-encoded internally, so we just
    decode the bytes to a UTF-8 string for JSON serialization.
    
    Args:
        plaintext: The token string to encrypt
        
    Returns:
        Fernet token as string (already base64-encoded by Fernet)
    """
    if not plaintext:
        return ""
    encrypted_bytes = encrypt_token(plaintext)
    # Fernet tokens are already base64-encoded, just decode bytes to string
    return encrypted_bytes.decode('utf-8')


def decrypt_token_from_storage(encrypted_data) -> str:
    """
    Decrypt a token retrieved from bytea storage via Supabase client.
    
    The data flow is:
    1. Storage: Fernet token (base64 string) → bytea column
    2. Retrieval: PostgreSQL returns bytea as hex string (\\x + hex chars)
    3. We need to: hex decode → get Fernet token bytes → Fernet decrypt
    
    Args:
        encrypted_data: Encrypted data from database (bytes or hex string)
        
    Returns:
        Decrypted plaintext token string
    """
    if not encrypted_data:
        return ""
    
    # If it's a string, it's hex-encoded from PostgreSQL
    if isinstance(encrypted_data, str):
        # Check if it starts with \x (hex prefix from PostgreSQL)
        if encrypted_data.startswith('\\x'):
            encrypted_data = encrypted_data[2:]  # Remove \x prefix
        
        # Decode from hex to get the Fernet token bytes
        try:
            # For NEW data (after this fix): hex string → Fernet token bytes
            encrypted_bytes = bytes.fromhex(encrypted_data)
        except ValueError:
            # For OLD data (double base64): try to decode
            try:
                hex_decoded = bytes.fromhex(encrypted_data)
                encrypted_bytes = base64.b64decode(hex_decoded)
            except:
                # Last resort: treat as base64 string
                cleaned_data = encrypted_data.replace('\n', '').replace('\r', '').replace(' ', '').replace('\t', '')
                missing_padding = (4 - len(cleaned_data) % 4) % 4
                if missing_padding:
                    cleaned_data += '=' * missing_padding
                encrypted_bytes = base64.b64decode(cleaned_data)
    else:
        # Already bytes from database
        encrypted_bytes = encrypted_data
    
    return decrypt_token(encrypted_bytes)
