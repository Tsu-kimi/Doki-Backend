# Supabase Auth Configuration for Google OAuth

## ⚠️ IMPORTANT: Required Supabase Setup

To make the OAuth flow work, you **MUST** configure Google as an auth provider in your Supabase project.

---

## 📋 Setup Steps

### 1. Enable Google Auth Provider in Supabase

1. Go to your Supabase Dashboard: https://supabase.com/dashboard
2. Select your project (`Doki`)
3. Navigate to **Authentication** → **Providers**
4. Find **Google** in the list of providers
5. Click to expand the Google provider settings

### 2. Configure Google Provider

You'll need the same Google OAuth credentials you're already using for the backend:

**From Google Cloud Console** (you already have these):
- Client ID: `<your-google-client-id>`
- Client Secret: `<your-google-client-secret>`

**In Supabase Google Provider Settings**:
1. **Enable** the toggle for Google provider
2. Paste your **Client ID** from Google Cloud Console
3. Paste your **Client Secret** from Google Cloud Console
4. Copy the **Authorized redirect URI** shown by Supabase (it looks like: `https://<your-project-ref>.supabase.co/auth/v1/callback`)
5. Click **Save**

### 3. Add Supabase Redirect URI to Google Cloud Console

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select your project
3. Navigate to **APIs & Services** → **Credentials**
4. Click on your OAuth 2.0 Client ID
5. Under **Authorized redirect URIs**, add the Supabase callback URL you copied in step 2:
   ```
   https://<your-project-ref>.supabase.co/auth/v1/callback
   ```
6. Click **Save**

---

## 🔧 How It Works Now

### Before (Broken):
```
User → /auth/google/login → Google OAuth → /auth/google/callback
                                                    ↓
                                            Expects JWT token (doesn't exist!)
                                                    ↓
                                            Falls back to test user ❌
```

### After (Fixed):
```
User → /auth/google/login → Google OAuth → /auth/google/callback
                                                    ↓
                                            Gets Google ID token
                                                    ↓
                                            Supabase Auth: sign_in_with_id_token()
                                                    ↓
                                            Creates/signs in real Supabase user ✅
                                                    ↓
                                            Returns Supabase JWT token ✅
```

---

## 🧪 Testing After Setup

### Step 1: Start Auth Flow
```bash
# Open in browser or curl
curl http://127.0.0.1:8000/auth/google/login
```

This will redirect to Google's consent screen.

### Step 2: After Google Sign-In
You'll be redirected back to `/auth/google/callback` which now returns:

```json
{
  "status": "authenticated",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "real-uuid-here",
    "email": "your-email@gmail.com"
  },
  "message": "Successfully authenticated with Supabase. Use the access_token for API requests."
}
```

### Step 3: Copy the JWT Token
**This is the JWT token you need!** Copy the `access_token` value.

### Step 4: Use in API Requests
```bash
export JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Now all connector endpoints work with your real user!
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://127.0.0.1:8000/connectors/sheets/list

curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://127.0.0.1:8000/connectors/supabase/test
```

---

## ✅ Verify It's Working

### Check 1: Supabase Users Table
Go to Supabase Dashboard → Authentication → Users

You should see:
- ✅ A **real user** with your Gmail address
- ✅ User ID is a **real UUID** (not all zeros!)
- ✅ Provider shows **google**

### Check 2: Profiles Table
Go to Supabase Dashboard → Table Editor → profiles

You should see:
- ✅ Profile created for your real user ID
- ✅ Email matches your Gmail
- ❌ NO test user with `00000000-0000-0000-0000-000000000000`

### Check 3: Credentials Table
Go to Supabase Dashboard → Table Editor → credentials

You should see:
- ✅ Google OAuth tokens stored
- ✅ `user_id` matches your real Supabase user ID
- ✅ `provider` = "google"
- ✅ `access_token_encrypted` and `refresh_token_encrypted` are populated

---

## 🐛 Troubleshooting

### Error: "ID token not found in OAuth response"
**Cause**: The OAuth flow didn't include `openid` scope.

**Solution**: This is now fixed in the code. Make sure you're using the updated auth.py with:
```python
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]
```

### Error: "Failed to authenticate with Supabase"
**Cause**: Google provider not enabled in Supabase or credentials mismatch.

**Solution**: Follow steps 1-3 above to configure Google auth provider in Supabase Dashboard.

### Still Seeing Test User?
**Cause**: You're making API calls without the JWT token.

**Solution**: 
1. Complete the OAuth flow to get your JWT token
2. Include it in all API requests: `Authorization: Bearer <your-jwt-token>`
3. Set `ENVIRONMENT=production` in `.env` to disable test user fallback

---

## 📚 Additional Resources

- [Supabase Auth with Google](https://supabase.com/docs/guides/auth/social-login/auth-google)
- [Sign in with ID Token](https://supabase.com/docs/reference/python/auth-signinwithidtoken)
- [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)

---

## 🎯 Summary of Changes

### What Changed in the Code:
1. ✅ Added `openid`, `userinfo.email`, `userinfo.profile` scopes to get ID token
2. ✅ Removed `Depends(get_current_user)` from callback (user isn't authenticated yet!)
3. ✅ Added `supabase.auth.sign_in_with_id_token()` to create/sign in Supabase user
4. ✅ Returns real Supabase JWT token in callback response
5. ✅ Stores Google tokens with real Supabase user ID

### What You Need to Do:
1. ⚙️ Enable Google auth provider in Supabase Dashboard
2. ⚙️ Add Supabase callback URL to Google Cloud Console
3. 🧪 Test the OAuth flow
4. 📋 Copy the JWT token from callback response
5. ✅ Use JWT token in all API requests

**After this setup, you'll have real Supabase Auth users instead of the test user!**
