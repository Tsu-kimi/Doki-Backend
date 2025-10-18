# 🔐 Authentication Implementation Guide

## Overview

Doki backend now supports **two authentication methods**:
1. **Email/Password Authentication** - Direct signup/signin with Supabase Auth
2. **Google OAuth** - Sign in with Google for Sheets access

---

## 📋 Authentication Flows

### 1. Email/Password Authentication

#### Sign Up Flow
```
Frontend → POST /auth/signup
Body: {
  "email": "user@example.com",
  "password": "secure123",
  "display_name": "John Doe"
}

Backend:
1. Calls supabase.auth.sign_up()
2. Stores display_name in user_metadata
3. Returns JWT token (if email confirmation disabled)
   OR pending_confirmation status

Response: {
  "status": "authenticated",
  "access_token": "<jwt_token>",
  "refresh_token": "<refresh_token>",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "John Doe"
  },
  "message": "Signup successful! You are now logged in."
}
```

#### Sign In Flow
```
Frontend → POST /auth/signin
Body: {
  "email": "user@example.com",
  "password": "secure123"
}

Backend:
1. Calls supabase.auth.sign_in_with_password()
2. Retrieves display_name from user_metadata
3. Returns JWT token

Response: {
  "status": "authenticated",
  "access_token": "<jwt_token>",
  "refresh_token": "<refresh_token>",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "display_name": "John Doe"
  },
  "message": "Sign in successful!"
}
```

#### Sign Out Flow
```
Frontend → POST /auth/signout
Headers: {
  "Authorization": "Bearer <jwt_token>"
}

Backend:
1. Validates JWT token
2. Calls supabase.auth.sign_out()
3. Invalidates session

Response: {
  "status": "signed_out",
  "message": "Successfully signed out"
}
```

---

### 2. Google OAuth Flow (for Sheets Access)

#### Initial Authentication
```
User clicks "Connect Google Sheets" button

Frontend → Redirects to /auth/google/login

Backend:
1. Generates OAuth URL with scopes:
   - openid
   - userinfo.email
   - userinfo.profile
   - drive.readonly
   - spreadsheets.readonly
2. Stores state in session
3. Redirects to Google

Google → User grants permissions → Redirects to /auth/google/callback

Backend:
1. Exchanges code for tokens (access, refresh, ID token)
2. Calls supabase.auth.sign_in_with_id_token() with Google ID token
3. Creates/signs in user in Supabase Auth
4. Stores encrypted Google OAuth tokens in credentials table
5. Returns Supabase JWT token

Response: {
  "status": "authenticated",
  "access_token": "<supabase_jwt>",
  "user": {
    "id": "uuid",
    "email": "user@example.com"
  },
  "message": "Successfully authenticated with Supabase..."
}
```

---

## 🔑 Token Management

### JWT Token Usage
All authenticated API requests must include:
```
Authorization: Bearer <jwt_token>
```

### Token Storage (Frontend)
```javascript
// After signup/signin/google callback
const { access_token, refresh_token, user } = response.data;

// Store in localStorage or secure cookie
localStorage.setItem('access_token', access_token);
localStorage.setItem('refresh_token', refresh_token);
localStorage.setItem('user', JSON.stringify(user));

// Include in all API requests
const headers = {
  'Authorization': `Bearer ${access_token}`,
  'Content-Type': 'application/json'
};
```

### Token Refresh
```javascript
// When access_token expires (check JWT exp claim)
// Use Supabase client to refresh:
const { data, error } = await supabase.auth.refreshSession({
  refresh_token: stored_refresh_token
});

if (data.session) {
  // Update stored tokens
  localStorage.setItem('access_token', data.session.access_token);
  localStorage.setItem('refresh_token', data.session.refresh_token);
}
```

---

## 🎯 User Journey

### New User (Email/Password)
1. **Sign Up**: POST /auth/signup with email, password, display_name
2. **Confirm Email** (if enabled in Supabase): Click link in email
3. **Sign In**: POST /auth/signin with email, password
4. **Use App**: Include JWT in all requests
5. **Connect Google**: Click button → /auth/google/login → Grant permissions
6. **Access Sheets**: Backend uses stored Google tokens

### Existing User (Returning)
1. **Sign In**: POST /auth/signin with email, password
2. **Use App**: Include JWT in all requests
3. **Google Already Connected**: Backend retrieves stored tokens automatically

### Google-Only User (First Time)
1. **Click "Sign in with Google"**: → /auth/google/login
2. **Grant Permissions**: Google OAuth consent screen
3. **Auto-Created in Supabase**: Backend creates user via sign_in_with_id_token()
4. **Use App**: Include JWT in all requests

---

## 🔒 Security Considerations

### Password Requirements
- Minimum 6 characters (enforced by Pydantic model)
- Supabase default: 6 characters minimum
- **Recommendation**: Increase to 8+ characters in production

### Email Confirmation
**Current**: Disabled for MVP (users can sign in immediately)
**Production**: Enable in Supabase Dashboard → Authentication → Email Auth Settings

To enable:
1. Go to Supabase Dashboard
2. Authentication → Providers → Email
3. Enable "Confirm email"
4. Configure email templates

### Token Security
- **Access Token**: Short-lived JWT (default 1 hour)
- **Refresh Token**: Long-lived, single-use
- **Storage**: Use httpOnly cookies in production (not localStorage)
- **Transmission**: HTTPS only in production

### Google OAuth Tokens
- Stored encrypted (Fernet) in `credentials` table
- Never exposed to frontend
- Backend retrieves and decrypts when accessing Sheets API
- Linked to user via `user_id` foreign key

---

## 📊 Database Schema

### auth.users (Supabase Auth)
```sql
-- Managed by Supabase Auth
id: uuid (primary key)
email: text (unique)
encrypted_password: text
email_confirmed_at: timestamp
raw_user_meta_data: jsonb  -- Contains display_name
created_at: timestamp
updated_at: timestamp
```

### public.profiles (Custom)
```sql
-- Auto-created via trigger on auth.users insert
id: uuid (FK to auth.users.id)
username: text (unique, nullable)
created_at: timestamp
updated_at: timestamp
```

### public.credentials (OAuth Tokens)
```sql
id: uuid (primary key)
user_id: uuid (FK to auth.users.id)
provider: text  -- 'google' or 'supabase'
access_token_encrypted: bytea
refresh_token_encrypted: bytea
expires_at: timestamp
scopes: text[]
created_at: timestamp
updated_at: timestamp
```

---

## 🧪 Testing

### Test Signup
```bash
curl -X POST http://127.0.0.1:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123",
    "display_name": "Test User"
  }'
```

**Expected Response**:
```json
{
  "status": "authenticated",
  "access_token": "eyJhbGc...",
  "refresh_token": "...",
  "user": {
    "id": "uuid-here",
    "email": "test@example.com",
    "display_name": "Test User"
  },
  "message": "Signup successful! You are now logged in."
}
```

### Test Sign In
```bash
curl -X POST http://127.0.0.1:8000/auth/signin \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "test123"
  }'
```

### Test Protected Endpoint
```bash
# Save token from signup/signin response
TOKEN="eyJhbGc..."

curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8000/connectors/sheets/list
```

### Test Sign Out
```bash
curl -X POST http://127.0.0.1:8000/auth/signout \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🚀 Frontend Integration

### React Example
```javascript
import { useState } from 'react';

function AuthForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const endpoint = isSignUp ? '/auth/signup' : '/auth/signin';
    const body = isSignUp 
      ? { email, password, display_name: displayName }
      : { email, password };

    try {
      const response = await fetch(`http://localhost:8000${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      const data = await response.json();

      if (response.ok) {
        // Store tokens
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        
        // Redirect to dashboard
        window.location.href = '/dashboard';
      } else {
        alert(data.detail || 'Authentication failed');
      }
    } catch (error) {
      console.error('Auth error:', error);
      alert('Network error');
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {isSignUp && (
        <input
          type="text"
          placeholder="Display Name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          required
        />
      )}
      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        minLength={6}
      />
      <button type="submit">
        {isSignUp ? 'Sign Up' : 'Sign In'}
      </button>
      <button type="button" onClick={() => setIsSignUp(!isSignUp)}>
        {isSignUp ? 'Already have an account?' : 'Need an account?'}
      </button>
      
      {/* Google OAuth Button */}
      <a href="http://localhost:8000/auth/google/login">
        <button type="button">Connect Google Sheets</button>
      </a>
    </form>
  );
}
```

---

## 📝 API Endpoints Summary

| Endpoint | Method | Auth Required | Purpose |
|----------|--------|---------------|---------|
| `/auth/signup` | POST | No | Create new user with email/password |
| `/auth/signin` | POST | No | Sign in with email/password |
| `/auth/signout` | POST | Yes | Sign out current user |
| `/auth/google/login` | GET | No | Initiate Google OAuth flow |
| `/auth/google/callback` | GET | No | Handle Google OAuth callback |

---

## ⚙️ Configuration

### Supabase Dashboard Settings

1. **Enable Email Auth**:
   - Go to Authentication → Providers → Email
   - Enable "Email" provider
   - Configure "Confirm email" (optional for MVP)

2. **Enable Google Auth** (for OAuth):
   - Go to Authentication → Providers → Google
   - Enable "Google" provider
   - Add Google Client ID and Secret
   - Copy Supabase callback URL
   - Add to Google Cloud Console authorized redirect URIs

3. **JWT Settings**:
   - Go to Settings → API
   - Note JWT Secret (for backend validation)
   - Configure JWT expiry (default 1 hour)

### Environment Variables
```bash
# Backend .env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=sb_secret_...
SUPABASE_JWT_SECRET=your-jwt-secret

# Google OAuth (for Sheets)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Encryption
ENCRYPTION_KEY=your-fernet-key

# Environment
ENVIRONMENT=development  # or production
```

---

## ✅ Summary

- **Email/Password auth** implemented with signup, signin, signout endpoints
- **Display name** stored in user_metadata during signup
- **Google OAuth** remains for Sheets access (separate flow)
- **JWT tokens** returned for all auth methods
- **Secure token storage** with Fernet encryption for OAuth tokens
- **Error handling** for common auth failures
- **Email confirmation** support (configurable in Supabase)
- **Frontend-ready** with clear API contracts

**Next Steps**:
1. Test endpoints with curl or Postman
2. Integrate frontend auth forms
3. Configure email templates in Supabase (if using confirmation)
4. Add password reset flow (future enhancement)
5. Implement token refresh logic in frontend
