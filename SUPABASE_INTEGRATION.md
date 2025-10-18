# 🔐 Supabase Integration - Service Role Key Architecture

## Overview

Doki integrates with user Supabase projects using the **service role key**, which provides privileged access that bypasses Row Level Security (RLS) policies. This document explains how this works and why no manual SQL setup is required.

---

## 🔑 Service Role Key Behavior

### What is the Service Role Key?

From [Supabase Documentation](https://supabase.com/docs/guides/api/api-keys):

> **service_role and secret keys**: These keys have elevated privileges and bypass Row Level Security. They should only be used on the server, never exposed to clients.

From [Supabase RLS Troubleshooting](https://supabase.com/docs/guides/troubleshooting/why-is-my-service-role-key-client-getting-rls-errors-or-not-returning-data-7_1K9z):

> **A Supabase client with the Authorization header set to the service role API key will ALWAYS bypass RLS.**

### ⚠️ Important: PostgREST Limitation

**While the service role key bypasses RLS, PostgREST (Supabase's REST API layer) does NOT expose system catalogs like `pg_catalog` or `information_schema` via the REST API.**

From [Supabase Custom Schemas Documentation](https://supabase.com/docs/guides/api/using-custom-schemas):

> By default, your database has a `public` schema which is automatically exposed on data APIs. Custom schemas must be explicitly exposed in API settings.

**System schemas (`pg_catalog`, `information_schema`) are never exposed via PostgREST**, even with service role key. This is a PostgREST design decision, not an RLS limitation.

**Solution**: Use RPC functions to query system catalogs. The service role key allows these RPC functions to access `information_schema` internally.

### How It Works

1. **Authorization Header**: When you create a Supabase client with the service role key:
   ```python
   client = create_client(project_url, service_role_key)
   ```
   
   The client sets:
   ```
   apikey: <service_role_key>
   Authorization: Bearer <service_role_key>
   ```

2. **RLS Bypass**: PostgREST sees the `Authorization` header contains the service role key and grants **unrestricted access** to:
   - All user tables (regardless of RLS policies)
   - System catalogs (`information_schema`, `pg_catalog`)
   - Full read/write permissions

3. **No Custom Functions Needed**: Unlike anon/authenticated keys which are restricted by RLS, the service role key can directly query:
   - `information_schema.columns` - table/column metadata
   - `pg_catalog.pg_tables` - table listings
   - Any other system views

---

## 🏗️ Implementation in Doki

### Connection Flow

```
User → Frontend → Backend API → Supabase (User's Project)
                      ↓
              Service Role Key
                      ↓
         Bypasses RLS → Full Access
```

### Code Structure

#### 1. Store Connection (`store_user_supabase_connection`)

```python
# User provides: project_url + service_role_key
# Backend:
# 1. Tests connection by attempting a query
test_client = create_client(project_url, service_role_key)
try:
    test_client.from_("_test").select("*").limit(0).execute()
except Exception as e:
    # "relation does not exist" = connection valid
    if "relation" in str(e) and "does not exist" in str(e):
        pass  # Connection works!

# 2. Encrypts service role key using Fernet
encrypted_key = encrypt_token_for_storage(service_role_key)

# 3. Stores in credentials table
data = {
    "user_id": user_id,
    "provider": "supabase",
    "access_token_encrypted": encrypted_key,
    "metadata": {"project_url": project_url}
}
```

#### 2. Test Connection (`test_user_supabase_connection`)

```python
# Retrieves encrypted key, decrypts, creates client
client = await get_user_supabase_client(user_id)

# Test with simple query
try:
    client.from_("_test").select("*").limit(0).execute()
except Exception as e:
    if "relation" in str(e) and "does not exist" in str(e):
        return True  # Connection valid!
```

#### 3. List Tables (`list_user_supabase_tables`)

```python
# Call RPC function to query information_schema
# The RPC function runs with SECURITY DEFINER, so it can access system catalogs
result = client.rpc('get_table_schema', {'target_schema': 'public'}).execute()

# ✅ RPC function required because PostgREST doesn't expose information_schema
# Service role allows the RPC function to access information_schema internally
```

**One-Time Setup Required**: Users must run `USER_SUPABASE_SETUP.sql` in their SQL Editor to create the `get_table_schema()` RPC function.

---

## 🔒 Security Considerations

### ✅ Safe Practices (Implemented)

1. **Backend-Only**: Service role key never sent to frontend
2. **Encrypted Storage**: Keys encrypted with Fernet before storing in database
3. **Secure Transport**: All API calls use HTTPS in production
4. **User Isolation**: Each user's credentials stored separately with `user_id` FK

### ⚠️ Important Warnings

1. **Key Leakage = Full Compromise**: If service role key leaks, attacker has unrestricted access to user's entire database
2. **No RLS Protection**: Service role operations bypass all RLS policies
3. **Logging Required**: All operations should be logged for audit trail
4. **Rate Limiting**: Implement rate limits to prevent abuse

### 🛡️ Mitigation Strategies

```python
# 1. Always validate user owns the connection
async def get_user_supabase_client(user_id: str):
    # Only returns client if user_id matches stored credentials
    response = supabase.table("credentials")\
        .eq("user_id", user_id)\
        .eq("provider", "supabase")\
        .execute()
    # ✅ Prevents user A from accessing user B's Supabase project

# 2. Encrypt at rest
encrypted_key = encrypt_token_for_storage(service_role_key)
# Uses Fernet symmetric encryption with ENCRYPTION_KEY from Secret Manager

# 3. Never log sensitive data
print(f"Test connection failed: {e}")  # ✅ Generic error
# ❌ DON'T: print(f"Failed with key: {service_role_key}")
```

---

## 📊 Comparison: Service Role vs RLS-Protected Access

| Aspect | Service Role Key | Anon/Authenticated Key |
|--------|------------------|------------------------|
| **RLS Bypass** | ✅ Always bypasses | ❌ Subject to RLS policies |
| **System Catalogs** | ✅ Full access | ❌ Restricted |
| **information_schema** | ✅ Direct queries | ❌ Need custom RPC functions |
| **Use Case** | Backend automation | Frontend user access |
| **Security Risk** | 🔴 High (if leaked) | 🟡 Medium (user-scoped) |
| **Exposure** | 🔒 Server-only | 🌐 Can be in client |

---

## 🧪 Testing

### Test Connection

```bash
curl -X POST http://127.0.0.1:8000/connectors/supabase/connect \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{
    "project_url": "https://yourproject.supabase.co",
    "service_role_key": "eyJhbGc..."
  }'
```

**Expected Response**:
```json
{
  "success": true,
  "message": "Supabase project connected successfully",
  "connection_id": "uuid-here"
}
```

### Test Connection Health

```bash
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://127.0.0.1:8000/connectors/supabase/test
```

**Expected Response**:
```json
{
  "status": "connected",
  "message": "Connection verified"
}
```

### List Tables

```bash
curl -H "Authorization: Bearer $JWT_TOKEN" \
  "http://127.0.0.1:8000/connectors/supabase/list?schema=public"
```

**Expected Response**:
```json
[
  {
    "name": "users",
    "columns": [
      {
        "name": "id",
        "type": "uuid",
        "is_nullable": false,
        "default_value": "gen_random_uuid()"
      },
      {
        "name": "email",
        "type": "text",
        "is_nullable": false,
        "default_value": null
      }
    ]
  }
]
```

---

## 🚀 Why This Approach Works

### One-Time Setup Required

**Setup Flow**:
1. User provides credentials (project_url + service_role_key)
2. Backend validates connection and stores encrypted credentials
3. **User runs `USER_SUPABASE_SETUP.sql` once** in their SQL Editor
4. Backend can now query schemas via RPC function

**Why the RPC function is needed**:
- PostgREST only exposes schemas configured in "Exposed schemas" setting
- System schemas (`pg_catalog`, `information_schema`) are never exposed
- RPC functions can access system catalogs internally with `SECURITY DEFINER`
- Service role key allows RPC execution without RLS restrictions

### Technical Explanation

**PostgREST Schema Exposure**:
```
✅ public schema → Exposed by default
✅ custom schemas → Must be added to "Exposed schemas" setting
❌ pg_catalog → Never exposed via REST API
❌ information_schema → Never exposed via REST API
```

**Solution - RPC Function**:
```sql
CREATE FUNCTION get_table_schema(target_schema text)
RETURNS TABLE (...) 
LANGUAGE plpgsql
SECURITY DEFINER  -- Runs with creator's privileges
AS $$
BEGIN
    -- Can query information_schema because of SECURITY DEFINER
    RETURN QUERY SELECT ... FROM information_schema.columns ...
END;
$$;
```

**When called with service role**:
```python
client = create_client(project_url, service_role_key)
result = client.rpc('get_table_schema', {'target_schema': 'public'}).execute()
```

PostgREST:
1. Validates service role key
2. Executes RPC function (bypasses RLS)
3. Function queries `information_schema` internally
4. Returns table/column metadata

This is **by design** - service role + RPC functions = full database introspection capability.

---

## 📚 References

- [Supabase API Keys Documentation](https://supabase.com/docs/guides/api/api-keys)
- [Service Role RLS Bypass Behavior](https://supabase.com/docs/guides/troubleshooting/why-is-my-service-role-key-client-getting-rls-errors-or-not-returning-data-7_1K9z)
- [PostgREST API Documentation](https://supabase.com/docs/guides/api)
- [Supabase Python Client](https://supabase.com/docs/reference/python/start)

---

## ✅ Summary

- **Service role key bypasses RLS** - documented Supabase behavior
- **RPC function for schema access** - PostgREST doesn't expose system catalogs
- **One-time SQL setup** - run `USER_SUPABASE_SETUP.sql` in SQL Editor
- **Backend-only usage** - never expose to frontend
- **Encrypted storage** - Fernet encryption at rest
- **User isolation** - credentials scoped by user_id
- **Simple connection** - project_url + service_role_key

**Result**: Minimal setup (one SQL script) for full database introspection! 🎉
