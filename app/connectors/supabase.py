"""
Supabase connectors: backend Supabase instance and user-provided Supabase projects.
"""
import os
from supabase import create_client, Client
from typing import List, Dict, Optional
from app.core.secrets import get_secret_value
from app.core.encryption import encrypt_token, decrypt_token
from app.models.connectors import TableSchema, TableColumn


def get_supabase_client() -> Client:
    """
    Create Supabase client for Doki's backend Supabase instance.
    Uses new secret key from Secret Manager.
    """
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL is not set")
    
    secret_key_name = os.getenv("SUPABASE_SECRET_KEY_NAME")
    if not secret_key_name:
        raise RuntimeError("SUPABASE_SECRET_KEY_NAME is not set")
    
    secret_key = get_secret_value(secret_key_name)
    return create_client(url, secret_key)


async def store_user_supabase_connection(
    user_id: str,
    project_url: str,
    anon_key: Optional[str],
    service_role_key: str
) -> str:
    """
    Store encrypted Supabase connection credentials for a user.
    
    Args:
        user_id: User's Supabase auth ID
        project_url: User's Supabase project URL
        anon_key: Optional anon/publishable key
        service_role_key: Required service role/secret key
        
    Returns:
        Connection ID (credentials record ID)
    """
    supabase = get_supabase_client()
    
    # Encrypt keys before storage
    encrypted_service_role = encrypt_token(service_role_key).hex()
    encrypted_anon = encrypt_token(anon_key).hex() if anon_key else None
    
    # Store in credentials table with provider="supabase"
    data = {
        "user_id": user_id,
        "provider": "supabase",
        "access_token_encrypted": encrypted_service_role,  # Using service role as access token
        "refresh_token_encrypted": encrypted_anon,  # Using anon key as refresh token (optional)
        "metadata": {"project_url": project_url},
    }
    
    response = supabase.table("credentials").insert(data).execute()
    
    if not response.data:
        raise ValueError("Failed to store Supabase connection")
    
    return response.data[0]["id"]


async def get_user_supabase_client(user_id: str) -> Optional[Client]:
    """
    Retrieve user's Supabase project credentials and create client.
    
    Args:
        user_id: User's Supabase auth ID
        
    Returns:
        Supabase Client for user's project or None if not found
    """
    supabase = get_supabase_client()
    
    # Fetch user's Supabase credentials
    response = supabase.table("credentials")\
        .select("*")\
        .eq("user_id", user_id)\
        .eq("provider", "supabase")\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()
    
    if not response.data or len(response.data) == 0:
        return None
    
    cred_data = response.data[0]
    
    # Decrypt service role key
    service_role_key = decrypt_token(bytes.fromhex(cred_data["access_token_encrypted"]))
    project_url = cred_data.get("metadata", {}).get("project_url")
    
    if not project_url:
        raise ValueError("Project URL not found in stored credentials")
    
    # Create client for user's Supabase project
    return create_client(project_url, service_role_key)


async def test_user_supabase_connection(user_id: str) -> bool:
    """
    Test if user's Supabase connection is valid.
    
    Args:
        user_id: User's Supabase auth ID
        
    Returns:
        True if connection is valid, False otherwise
    """
    try:
        client = await get_user_supabase_client(user_id)
        if not client:
            return False
        
        # Simple query to test connection
        # Query information_schema to verify access
        result = client.table("information_schema.tables")\
            .select("table_name")\
            .limit(1)\
            .execute()
        
        return True
    except Exception:
        return False


async def list_user_supabase_tables(user_id: str, schema: str = "public") -> List[TableSchema]:
    """
    List all tables and columns from user's Supabase project.
    
    Args:
        user_id: User's Supabase auth ID
        schema: PostgreSQL schema to query (default: public)
        
    Returns:
        List of TableSchema objects with columns
        
    Raises:
        ValueError: If connection not found or query fails
    """
    client = await get_user_supabase_client(user_id)
    if not client:
        raise ValueError("Supabase connection not found for user")
    
    try:
        # Query information_schema for table and column information
        query = f"""
        SELECT 
            c.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default
        FROM information_schema.columns c
        WHERE c.table_schema = '{schema}'
        ORDER BY c.table_name, c.ordinal_position
        """
        
        # Execute raw SQL via RPC or use PostgREST directly
        # Note: Supabase Python client doesn't have direct SQL execution
        # We'll use a workaround with RPC function or direct REST API
        
        # Alternative: Use direct PostgreSQL query via rpc
        # For now, we'll use a simpler approach with table introspection
        
        # Get list of tables first
        tables_response = client.table("information_schema.tables")\
            .select("table_name")\
            .eq("table_schema", schema)\
            .eq("table_type", "BASE TABLE")\
            .execute()
        
        if not tables_response.data:
            return []
        
        table_schemas = []
        
        for table_row in tables_response.data:
            table_name = table_row["table_name"]
            
            # Get columns for this table
            columns_response = client.table("information_schema.columns")\
                .select("column_name, data_type, is_nullable, column_default")\
                .eq("table_schema", schema)\
                .eq("table_name", table_name)\
                .order("ordinal_position")\
                .execute()
            
            columns = [
                TableColumn(
                    name=col["column_name"],
                    type=col["data_type"],
                    is_nullable=(col["is_nullable"] == "YES"),
                    default_value=col.get("column_default")
                )
                for col in columns_response.data
            ]
            
            table_schemas.append(TableSchema(
                table_name=table_name,
                schema=schema,
                columns=columns
            ))
        
        return table_schemas
        
    except Exception as e:
        raise ValueError(f"Failed to fetch Supabase schema: {str(e)}")
