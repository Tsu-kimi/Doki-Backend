"""
Supabase connectors: backend Supabase instance and user-provided Supabase projects.
"""
import os
import requests
from supabase import create_client, Client
from typing import List, Dict, Optional
from app.core.secrets import get_secret_value
from app.core.encryption import encrypt_token_for_storage, decrypt_token_from_storage
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
    # Note: Supabase client requires JSON-serializable values, so we use base64 encoding
    encrypted_service_role = encrypt_token_for_storage(service_role_key)
    encrypted_anon = encrypt_token_for_storage(anon_key) if anon_key else None
    
    # Store in credentials table with provider="supabase"
    data = {
        "user_id": user_id,
        "provider": "supabase",
        "access_token_encrypted": encrypted_service_role,  # Using service role as access token
        "refresh_token_encrypted": encrypted_anon,  # Using anon key as refresh token (optional)
        "metadata": {"project_url": project_url},
    }
    
    # Test the connection by making a simple query
    # Note: PostgREST doesn't expose pg_catalog/information_schema via REST API
    # We'll query a known public table or use RPC to validate connection
    try:
        test_client = create_client(project_url, service_role_key)
        # Try to query any table in public schema (even if empty)
        # This validates the credentials and project URL
        # If no tables exist, this will still succeed with empty result
        try:
            test_client.from_("_nonexistent_table_test").select("*").limit(0).execute()
        except Exception as table_err:
            # Expected error if table doesn't exist, but connection is valid
            # Check if it's a connection error vs table not found
            error_msg = str(table_err).lower()
            if "relation" in error_msg and "does not exist" in error_msg:
                # Table doesn't exist but connection works - this is fine
                pass
            else:
                # Real connection error
                raise
    except Exception as e:
        raise ValueError(f"Failed to connect to Supabase project: {str(e)}")
    
    # Store credentials
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
    # decrypt_token_from_storage handles both bytes and base64-encoded strings
    service_role_key = decrypt_token_from_storage(cred_data["access_token_encrypted"])
    project_url = cred_data.get("metadata", {}).get("project_url")
    
    if not project_url:
        raise ValueError("Project URL not found in stored credentials")
    
    # Create client for user's Supabase project
    return create_client(project_url, service_role_key)


async def test_user_supabase_connection(user_id: str) -> bool:
    """
    Test if user's Supabase connection is valid.
    
    Note: PostgREST doesn't expose system catalogs via REST API.
    We test by attempting a simple query.
    
    Args:
        user_id: User's Supabase auth ID
        
    Returns:
        True if connection is valid, False otherwise
    """
    try:
        client = await get_user_supabase_client(user_id)
        if not client:
            return False
        
        # Test connection with a simple query
        # Even if table doesn't exist, a valid connection will return an error we can recognize
        try:
            client.from_("_test").select("*").limit(0).execute()
        except Exception as e:
            error_msg = str(e).lower()
            # If we get "relation does not exist", connection is valid
            if "relation" in error_msg and "does not exist" in error_msg:
                return True
            # Other errors might indicate connection issues
            raise
        
        return True
    except Exception as e:
        print(f"Test connection failed: {e}")
        return False


async def list_user_supabase_tables(user_id: str, schema: str = "public") -> List[TableSchema]:
    """
    List all tables and columns from user's Supabase project.
    
    Uses service role key which bypasses RLS to directly query information_schema.
    
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
        # PostgREST doesn't expose information_schema via REST API
        # We need to use an RPC function to query system catalogs
        # First, try to call a helper function (we'll create it if needed)
        
        try:
            result = client.rpc('get_table_schema', {'target_schema': schema}).execute()
            
            if not result.data:
                return []
            
            # Group columns by table
            tables_dict = {}
            for row in result.data:
                table_name = row['table_name']
                if table_name not in tables_dict:
                    tables_dict[table_name] = []
                
                tables_dict[table_name].append({
                    'name': row['column_name'],
                    'type': row['data_type'],
                    'nullable': row['is_nullable'] == 'YES',
                    'default': row.get('column_default')
                })
            
            # Convert to TableSchema objects
            table_schemas = [
                TableSchema(table_name=table_name, columns=[
                    TableColumn(
                        name=col["name"],
                        type=col["type"],
                        is_nullable=col["nullable"],
                        default_value=col.get("default")
                    )
                    for col in columns
                ])
                for table_name, columns in tables_dict.items()
            ]
            
            return table_schemas
            
        except Exception as rpc_error:
            # RPC function doesn't exist - need to create it
            if 'function' in str(rpc_error).lower() and 'does not exist' in str(rpc_error).lower():
                raise ValueError(
                    "Schema introspection requires a database function. "
                    "Please create the 'get_table_schema' function in your Supabase project. "
                    "Run this SQL in your SQL Editor:\n\n"
                    "CREATE OR REPLACE FUNCTION get_table_schema(target_schema text DEFAULT 'public')\n"
                    "RETURNS TABLE (table_name text, column_name text, data_type text, is_nullable text, column_default text)\n"
                    "LANGUAGE plpgsql SECURITY DEFINER AS $$\n"
                    "BEGIN\n"
                    "  RETURN QUERY SELECT c.table_name::text, c.column_name::text, c.data_type::text, "
                    "c.is_nullable::text, c.column_default::text FROM information_schema.columns c "
                    "WHERE c.table_schema = target_schema ORDER BY c.table_name, c.ordinal_position;\n"
                    "END; $$;\n\n"
                    "GRANT EXECUTE ON FUNCTION get_table_schema(text) TO authenticated, service_role;"
                )
            raise
        
    except Exception as e:
        raise ValueError(f"Failed to fetch schema: {str(e)}")
