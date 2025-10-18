# Doki Backend Testing Guide

## 🔑 Getting JWT Tokens for API Testing

### Method 1: Development Mode (Easiest for Local Testing)

The backend includes a development fallback that allows testing without JWT tokens:

1. **Set environment to development**:
   ```bash
   # In .env file
   ENVIRONMENT=development
   ```

2. **Make requests without Authorization header**:
   ```bash
   # This will use the test user automatically in development
   curl http://127.0.0.1:8000/connectors/sheets/list
   ```

3. **Test user details** (auto-injected in development):
   - `user_id`: `00000000-0000-0000-0000-000000000000`
   - `email`: `test@doki-mvp.local`
   - `role`: `authenticated`

⚠️ **Warning**: This only works when `ENVIRONMENT != "production"`. Always use real JWT tokens in production.

---

### Method 2: Supabase Auth (Production Flow)

For production-like testing with real user authentication:

#### Step 1: Create a Test User in Supabase

Go to your Supabase Dashboard:
1. Navigate to **Authentication** → **Users**
2. Click **Add User** → **Create new user**
3. Enter email and password
4. Note the user's UUID (this is their `user_id`)

#### Step 2: Get JWT Token via Supabase Client

**Option A: Using Supabase Dashboard**
1. Go to **Authentication** → **Users**
2. Click on your test user
3. Copy the **Access Token (JWT)** from the user details

**Option B: Using Supabase CLI**
```bash
# Sign in as the test user
npx supabase functions invoke --project-ref YOUR_PROJECT_REF \
  auth/v1/token \
  --data '{"email":"test@example.com","password":"yourpassword"}'
```

**Option C: Using curl (Direct API)**
```bash
curl -X POST 'https://YOUR_PROJECT_ID.supabase.co/auth/v1/token?grant_type=password' \
  -H 'apikey: YOUR_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "test@example.com",
    "password": "yourpassword"
  }'
```

Response will include:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "refresh_token": "...",
  "user": {...}
}
```

#### Step 3: Use JWT Token in Requests

```bash
# Store token in variable
export JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Use in API calls
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://127.0.0.1:8000/connectors/sheets/list
```

---

### Method 3: Frontend Integration (Real Flow)

In production, the frontend handles authentication:

```typescript
// Frontend: Next.js with Supabase Auth
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

// Sign in user
const { data, error } = await supabase.auth.signInWithPassword({
  email: 'user@example.com',
  password: 'password'
})

// Get JWT token
const session = data.session
const jwtToken = session.access_token

// Make backend API call
const response = await fetch('http://api.doki.com/connectors/sheets/list', {
  headers: {
    'Authorization': `Bearer ${jwtToken}`
  }
})
```

---

## 🔐 Service Role vs User-Level Access

### Current Implementation

The Doki backend uses **two levels of access**:

#### 1. Backend Service Role (RLS Bypass)
- **Purpose**: Backend operations that need elevated access
- **Key**: `SUPABASE_SECRET_KEY_NAME` (stored in Secret Manager)
- **Used by**: 
  - `app/connectors/supabase.py` → `get_supabase_client()`
  - Backend logging, sync operations
  - Credential storage/retrieval
- **RLS**: **BYPASSED** - Service role has full access

```python
# Example: Backend writing logs (bypasses RLS)
from app.connectors.supabase import get_supabase_client

supabase = get_supabase_client()  # Uses service role key
supabase.table("logs").insert({
    "user_id": user_id,
    "message": "Sync completed",
    "level": "info"
}).execute()  # ✅ Works even with RLS enabled
```

#### 2. User-Level Access (RLS Enforced)
- **Purpose**: User-specific data access with row-level security
- **Key**: User's JWT token (obtained via Supabase Auth)
- **Used by**: Frontend, user-scoped operations
- **RLS**: **ENFORCED** - Users can only access their own data

```typescript
// Example: Frontend reading user's sync configs (RLS enforced)
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)
await supabase.auth.signInWithPassword({...})

const { data } = await supabase
  .from('sync_configs')
  .select('*')  // ✅ RLS policy only returns user's own configs
```

---

## 🛡️ RLS Policies Verification

Your Supabase tables already have RLS enabled with owner-scoped policies:

### Current RLS Policies

```sql
-- profiles: Users can read/update their own profile
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own profile" ON profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own profile" ON profiles FOR UPDATE USING (auth.uid() = id);

-- credentials: Full access to own credentials
CREATE POLICY "Users have full access to own credentials" ON credentials 
  FOR ALL USING (auth.uid() = user_id);

-- sync_configs: Full access to own sync configs
CREATE POLICY "Users have full access to own sync_configs" ON sync_configs 
  FOR ALL USING (auth.uid() = user_id);

-- logs: Read access via ownership chain
CREATE POLICY "Users can view own logs" ON logs FOR SELECT
  USING (auth.uid() IN (
    SELECT user_id FROM sync_configs WHERE id = logs.sync_config_id
  ) OR auth.uid() = user_id);
```

### Service Role Bypass
The backend's service role key (`SUPABASE_SECRET_KEY`) automatically bypasses all RLS policies. No configuration needed.

---

## 🧪 Complete Testing Examples

### 1. OAuth Flow (Google Sheets)

```bash
# Step 1: Initiate OAuth (opens browser)
curl http://127.0.0.1:8000/auth/google/login

# Step 2: After OAuth callback, get JWT token (see above methods)

# Step 3: List spreadsheets
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://127.0.0.1:8000/connectors/sheets/list

# Expected Response:
[
  {
    "id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
    "name": "My Spreadsheet",
    "modified_time": "2025-10-17T12:00:00Z",
    "web_view_link": "https://docs.google.com/spreadsheets/d/..."
  }
]

# Step 4: Get spreadsheet schema
curl -H "Authorization: Bearer $JWT_TOKEN" \
  "http://127.0.0.1:8000/connectors/sheets/schema?spreadsheet_id=1DpXl-YSjpOepkyXdUuiN9y8ZVVPUoAQJqzkZf1gIHgQ"

# Expected Response:
{
  "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
  "title": "My Spreadsheet",
  "sheets": [
    {
      "sheet_name": "Sheet1",
      "sheet_id": 0,
      "columns": [
        {"name": "Name", "index": 0},
        {"name": "Email", "index": 1}
      ]
    }
  ]
}
```

### 2. Supabase User Connector

```bash
# Step 1: Connect user's Supabase project
curl -X POST http://127.0.0.1:8000/connectors/supabase/connect \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_url": "https://myproject.supabase.co",
    "service_role_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }'

# Expected Response:
{
  "success": true,
  "message": "Supabase project connected successfully",
  "connection_id": "uuid-here"
}

# Step 2: Test connection
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://127.0.0.1:8000/connectors/supabase/test

# Expected Response:
{
  "status": "connected",
  "message": "Connection verified"
}

# Step 3: List tables
curl -H "Authorization: Bearer $JWT_TOKEN" \
  "http://127.0.0.1:8000/connectors/supabase/list?schema=public"

# Expected Response:
[
  {
    "table_name": "customers",
    "schema_name": "public",
    "columns": [
      {"name": "id", "type": "uuid", "is_nullable": false, "default_value": null},
      {"name": "email", "type": "text", "is_nullable": true, "default_value": null}
    ]
  }
]
```

---

## ❌ Error Handling

### 401 Unauthorized (Token Issues)

```bash
# Expired or invalid token
curl -H "Authorization: Bearer invalid_token" \
  http://127.0.0.1:8000/connectors/sheets/list

# Response:
{
  "detail": "Invalid authentication credentials: Token has expired"
}
```

**Solution**: Get a fresh JWT token (see Method 2 above)

### 401 Google Credentials Not Found

```bash
# User hasn't completed OAuth flow
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://127.0.0.1:8000/connectors/sheets/list

# Response:
{
  "detail": "Google credentials not found for user"
}
```

**Solution**: Complete OAuth flow via `/auth/google/login`

### 404 Supabase Connection Not Found

```bash
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://127.0.0.1:8000/connectors/supabase/list

# Response:
{
  "detail": "Supabase connection not found for user"
}
```

**Solution**: Connect Supabase project via `/connectors/supabase/connect`

---

## 🚀 Quick Start Commands

```bash
# 1. Start backend
uvicorn app.main:app --reload

# 2. Set up test user (development mode)
export ENVIRONMENT=development

# 3. Test without auth (dev only)
curl http://127.0.0.1:8000/connectors/sheets/list

# 4. For production testing, get JWT token first:
export JWT_TOKEN=$(curl -X POST 'https://YOUR_PROJECT.supabase.co/auth/v1/token?grant_type=password' \
  -H 'apikey: YOUR_ANON_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"yourpassword"}' \
  | jq -r '.access_token')

# 5. Use JWT in requests
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://127.0.0.1:8000/connectors/sheets/list
```

---

## 📚 Additional Resources

- **Supabase Auth Docs**: https://supabase.com/docs/guides/auth
- **JWT Validation**: https://supabase.com/docs/guides/auth/jwts
- **RLS Policies**: https://supabase.com/docs/guides/database/postgres/row-level-security
- **FastAPI Dependencies**: https://fastapi.tiangolo.com/tutorial/dependencies/
