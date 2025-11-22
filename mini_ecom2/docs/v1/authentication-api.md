# Mini E-commerce Authentication API - Complete Documentation

## Table of Contents
1. [Overview](#overview)
2. [Authentication Methods](#authentication-methods)
3. [Getting Started](#getting-started)
4. [Account Management](#account-management)
5. [Two-Factor Authentication (2FA)](#two-factor-authentication-2fa)
6. [Social Authentication](#social-authentication)
7. [Phone Verification](#phone-verification)
8. [Email Management](#email-management)
9. [Error Handling](#error-handling)
10. [Rate Limiting](#rate-limiting)
11. [Security Best Practices](#security-best-practices)

---

## Overview

This API provides comprehensive authentication and user management features built with Django REST Framework and Django Allauth.

### Base URL
```
Development: http://localhost:8000
Production: https://api.yourdomain.com
```

### Key Features
- ✅ Email/Password Authentication with mandatory email verification
- ✅ Social Authentication (Google, Facebook) with optional 2FA
- ✅ Time-based One-Time Password (TOTP) 2FA
- ✅ SMS-based phone verification
- ✅ JWT token authentication (access + refresh tokens)
- ✅ Cookie-based and header-based token delivery
- ✅ Profile management with image uploads
- ✅ Email change with re-verification
- ✅ Comprehensive rate limiting

### Technology Stack
- **Backend**: Django 5.2.8, Django REST Framework
- **Authentication**: Django Allauth, dj-rest-auth
- **2FA**: django-otp (TOTP + Static backup codes)
- **Phone**: phonenumber-field, Twilio (optional)
- **Tokens**: djangorestframework-simplejwt
- **Caching**: Redis (django-redis)

---

## Authentication Methods

### 1. JWT Token Authentication

The API supports two token delivery methods:

#### Header-Based (Mobile/API Clients)
```http
Authorization: Bearer <access_token>
```

#### Cookie-Based (Web Clients)
Tokens are automatically stored in httpOnly cookies:
- `jwt-auth`: Access token
- `jwt-refresh`: Refresh token

### 2. Token Lifetimes
| Token Type | Lifetime | Rotation |
|-----------|----------|----------|
| Access Token | 60 minutes | No |
| Refresh Token | 7 days | Yes (on refresh) |

### 3. Session Configuration
- **Engine**: Cached database sessions with Redis
- **Lifetime**: 14 days
- **Cookie Settings**: httpOnly, SameSite=Lax, Secure (production)

---

## Getting Started

### Prerequisites
- Valid email address for verification
- Phone number (optional, for phone verification)
- Google/Facebook account (optional, for social login)
- Authenticator app (optional, for 2FA setup)

### Quick Start Flow

```
1. Register → 2. Verify Email → 3. Login → 4. Setup Profile
                                    ↓
                         (Optional) Enable 2FA
                         (Optional) Add Phone Number
```

---

## Account Management

### 1. User Registration

Register a new user account with mandatory email verification.

**Endpoint:** `POST /api/auth/register/`

**Throttling:** 10 requests per day per IP

**Request Body:**
```json
{
  "email": "user@example.com",
  "username": "john_doe",
  "password1": "SecurePass123!@#",
  "password2": "SecurePass123!@#",
  "display_name": "John Doe",
  "phone_number": "+2348012345678"
}
```

**Field Requirements:**
- `email` **(required)**: Must be unique and valid
- `username` **(required)**: 150 characters max, alphanumeric + @/./+/-/_
- `password1` **(required)**: Min 8 characters, must meet Django validators
- `password2` **(required)**: Must match password1
- `display_name` *(optional)*: 50 characters max, used for display
- `phone_number` **(required)**: E.164 format, must be unique

**Success Response (201 Created):**
```json
{
  "detail": "Verification email sent.",
  "user": {
    "pk": 1,
    "email": "user@example.com",
    "username": "john_doe"
  }
}
```

**Error Responses:**

*400 Bad Request - Email exists:*
```json
{
  "email": ["A user is already registered with this email address."]
}
```

*400 Bad Request - Username exists:*
```json
{
  "username": ["A user with that username already exists."]
}
```

*400 Bad Request - Phone exists:*
```json
{
  "phone_number": ["This phone number is already registered."]
}
```

*400 Bad Request - Password mismatch:*
```json
{
  "non_field_errors": ["The two password fields didn't match."]
}
```

*400 Bad Request - Weak password:*
```json
{
  "password1": [
    "This password is too common.",
    "This password is entirely numeric."
  ]
}
```

**Important Notes:**
- User account is created but inactive until email verification
- Verification email expires in 3 days
- User cannot login until email is verified
- Phone number is stored but not verified (requires separate verification)

---

### 2. Email Verification

Verify email address using the link sent to registered email.

**Endpoint:** `GET /accounts/confirm-email/<key>/`

**Method:** Link click (GET request from email)

**Flow:**
1. User clicks verification link in email
2. Backend validates the key
3. User is redirected to frontend with verification status

**Success Redirect:**
```
http://localhost:3000/email-verified/
```

**Process:**
- Sets `user.is_active = True`
- Marks email as `verified` in `EmailAddress` table
- Allows user to login

**Error Cases:**
- **Invalid/Expired Key**: Redirects with error parameter
- **Already Verified**: Shows "Email already confirmed" message

**Testing in Development:**
```bash
# Email is printed to console
# Look for: "http://localhost:8000/accounts/confirm-email/..."
# Click or paste into browser
```

---

### 3. Login

Authenticate user and receive JWT tokens.

**Endpoint:** `POST /api/auth/login/`

**Throttling:** 5 requests per minute per IP

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!@#"
}
```

**Success Response (200 OK) - Without 2FA:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "pk": 1,
    "email": "user@example.com",
    "username": "john_doe",
    "first_name": "John",
    "last_name": "Doe",
    "display_name": "John Doe",
    "phone_number": "+2348012345678",
    "phone_verified": true,
    "date_of_birth": "1990-01-15",
    "profile_picture": "http://localhost:8000/media/profile_picture/user.jpg",
    "social_accounts": [],
    "has_2fa": false
  }
}
```

**Success Response (202 Accepted) - With 2FA Enabled:**
```json
{
  "detail": "2FA verification required",
  "requires_2fa": true,
  "user_id": 1
}
```

**Error Responses:**

*400 Bad Request - Invalid credentials:*
```json
{
  "non_field_errors": [
    "Unable to log in with provided credentials."
  ]
}
```

*403 Forbidden - Email not verified:*
```json
{
  "detail": "User account is inactive. Please verify email address.",
  "verification_required": true,
  "email": "user@example.com"
}
```

*403 Forbidden - Account disabled:*
```json
{
  "detail": "User account is disabled."
}
```

**Cookie Behavior:**
- Web clients receive tokens in httpOnly cookies
- Mobile clients should extract tokens from response body
- Cookies have SameSite=Lax attribute

**Next Steps:**
- **Without 2FA**: Use access token for authenticated requests
- **With 2FA**: Proceed to verify 2FA code

---

### 4. Login with 2FA Verification

Complete login when 2FA is enabled.

**Endpoint:** `POST /api/auth/login/`

**Request Body:**
```json
{
  "user_id": 1,
  "otp_verified": true,
  "token": "123456"
}
```

**Alternative Field Names:**
```json
{
  "user_id": 1,
  "otp_verified": true,
  "otp_token": "123456"
}
```

**Token Types:**
- **TOTP Code**: 6-digit numeric code from authenticator app
- **Backup Code**: 8-character alphanumeric code

**Success Response (200 OK) - TOTP:**
```json
{
  "detail": "Login successful",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "user@example.com",
    "display_name": "John Doe"
  },
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Success Response (200 OK) - Backup Code:**
```json
{
  "detail": "Login successful",
  "warning": "Backup code used. Please generate new backup codes",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "user@example.com",
    "display_name": "John Doe"
  },
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Error Responses:**

*400 Bad Request - Missing fields:*
```json
{
  "detail": "User ID and token required"
}
```

*400 Bad Request - Invalid token:*
```json
{
  "detail": "Invalid 2FA token."
}
```

*403 Forbidden - Account disabled:*
```json
{
  "detail": "User account disabled"
}
```

**Important Notes:**
- TOTP codes expire after 30 seconds (standard TOTP behavior)
- Backup codes can only be used once
- Failed attempts don't lock the account but may trigger rate limiting
- Session is marked with `otp_verified` flag

---

### 5. Refresh Token

Obtain new access token using refresh token.

**Endpoint:** `POST /api/auth/token/refresh/`

**Request Body:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Success Response (200 OK):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Error Responses:**

*401 Unauthorized - Invalid/Expired token:*
```json
{
  "detail": "Token is invalid or expired",
  "code": "token_not_valid"
}
```

*401 Unauthorized - Blacklisted token:*
```json
{
  "detail": "Token is blacklisted",
  "code": "token_not_valid"
}
```

**Token Rotation:**
- Each refresh issues a new refresh token
- Old refresh token is automatically blacklisted
- Prevents token reuse attacks

**Best Practices:**
- Refresh before access token expires (proactive refresh)
- Store new refresh token securely
- Handle 401 errors by re-authenticating user

---

### 6. Logout

Invalidate refresh token and clear session.

**Endpoint:** `POST /api/auth/logout/`

**Authentication:** Required

**Request Body:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Success Response (200 OK):**
```json
{
  "detail": "Successfully logged out."
}
```

**Error Responses:**

*400 Bad Request - Missing refresh token:*
```json
{
  "refresh": ["This field is required."]
}
```

*401 Unauthorized - Invalid token:*
```json
{
  "detail": "Token is invalid or expired"
}
```

**Process:**
- Blacklists the provided refresh token
- Clears session data
- Clears authentication cookies (web clients)
- Access token remains valid until expiry

**Important:**
- Client must discard access token after logout
- Access token cannot be invalidated server-side (JWT limitation)
- Session-based data (2FA verification) is cleared

---

### 7. User Profile

Retrieve and update authenticated user's profile.

**Endpoint:** `GET/PUT/PATCH /api/accounts/profile/`

**Authentication:** Required

**GET Response (200 OK):**
```json
{
  "id": 1,
  "user": {
    "email": "user@example.com",
    "username": "john_doe"
  },
  "first_name": "John",
  "last_name": "Doe",
  "gender": "male",
  "bio": "Software developer passionate about APIs",
  "date_of_birth": "1990-01-15",
  "profile_picture": "http://localhost:8000/media/profile_picture/john.jpg",
  "phone_number": "+2348012345678",
  "phone_verified": true,
  "created_at": "2025-01-01T10:30:00Z",
  "updated_at": "2025-01-15T14:20:00Z"
}
```

**PUT/PATCH Request:**

*Content-Type: `application/json`*
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "gender": "male",
  "bio": "Senior software developer",
  "date_of_birth": "1990-01-15"
}
```

*Content-Type: `multipart/form-data` (for file upload)*
```
first_name: John
last_name: Doe
gender: male
bio: Senior software developer
date_of_birth: 1990-01-15
profile_picture: <binary file data>
```

**Field Specifications:**

| Field | Type | Max Length | Choices | Validation |
|-------|------|------------|---------|------------|
| `first_name` | string | 150 | - | - |
| `last_name` | string | 150 | - | - |
| `gender` | string | 20 | male, female, rather_not_say | - |
| `bio` | text | unlimited | - | - |
| `date_of_birth` | date | - | - | Cannot be future date |
| `profile_picture` | image | 5MB | jpg, jpeg, png | Auto-resized to 512x512 |

**Success Response (200 OK):**
```json
{
  "id": 1,
  "user": {
    "email": "user@example.com",
    "username": "john_doe"
  },
  "first_name": "John",
  "last_name": "Doe",
  "gender": "male",
  "bio": "Senior software developer",
  "date_of_birth": "1990-01-15",
  "profile_picture": "http://localhost:8000/media/profile_picture/john.jpg",
  "phone_number": "+2348012345678",
  "phone_verified": true,
  "created_at": "2025-01-01T10:30:00Z",
  "updated_at": "2025-01-15T14:25:30Z"
}
```

**Error Responses:**

*400 Bad Request - Invalid date:*
```json
{
  "date_of_birth": ["Date of birth cannot be in the future."]
}
```

*400 Bad Request - Invalid image:*
```json
{
  "profile_picture": [
    "Upload a valid image. The file you uploaded was either not an image or a corrupted image."
  ]
}
```

*400 Bad Request - File too large:*
```json
{
  "profile_picture": ["File size must be under 5MB."]
}
```

*400 Bad Request - Invalid gender:*
```json
{
  "gender": ["\"other\" is not a valid choice."]
}
```

**Image Processing:**
- Uploaded images are automatically resized to 512x512 pixels
- JPEG quality set to 85% for optimization
- Thumbnail generation preserves aspect ratio
- Original aspect ratio maintained, image centered

**Profile Picture URL:**
- Social login users: Google/Facebook avatar URL (if available)
- Regular users: Uploaded profile picture or null
- URL is absolute and includes domain

---

### 8. Password Management

#### 8.1 Change Password (Authenticated)

Change password for logged-in users.

**Endpoint:** `POST /api/auth/password/change/`

**Authentication:** Required

**Request Body:**
```json
{
  "old_password": "OldSecurePass123!",
  "new_password1": "NewSecurePass456!",
  "new_password2": "NewSecurePass456!"
}
```

**Success Response (200 OK):**
```json
{
  "detail": "New password has been saved."
}
```

**Error Responses:**

*400 Bad Request - Incorrect old password:*
```json
{
  "old_password": ["Your old password was entered incorrectly. Please enter it again."]
}
```

*400 Bad Request - Password mismatch:*
```json
{
  "new_password2": ["The two password fields didn't match."]
}
```

*400 Bad Request - Weak password:*
```json
{
  "new_password1": [
    "This password is too short. It must contain at least 8 characters.",
    "This password is too common."
  ]
}
```

**Important Notes:**
- User remains logged in after password change (`LOGOUT_ON_PASSWORD_CHANGE = False`)
- All existing sessions remain valid
- Existing JWT tokens remain valid until expiry
- Consider forcing re-login for security-sensitive applications

---

#### 8.2 Request Password Reset

Request password reset for forgotten passwords.

**Endpoint:** `POST /api/auth/password/reset/`

**Throttling:** 5 requests per hour per IP

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Success Response (200 OK):**
```json
{
  "detail": "Password reset e-mail has been sent."
}
```

**Important Notes:**
- Always returns success (security best practice)
- Email sent only if account exists
- Reset link expires in 1 hour (`PASSWORD_RESET_TIMEOUT = 3600`)
- Works even for inactive accounts
- Does not reveal if email exists

**Email Content:**
```
Subject: [Mini E-com] Password Reset

You're receiving this email because you requested a password reset.
Please click the link below:

http://localhost:8000/api/auth/password/reset/confirm/<uid>/<token>/

If you didn't request this, please ignore this email.
```

---

#### 8.3 Confirm Password Reset

Complete password reset using link from email.

**Endpoint:** `POST /api/auth/password/reset/confirm/`

**Request Body:**
```json
{
  "uid": "MQ",
  "token": "c6h0rz-58d2c1234567890abcdef1234567890",
  "new_password1": "NewSecurePass789!",
  "new_password2": "NewSecurePass789!"
}
```

**Success Response (200 OK):**
```json
{
  "detail": "Password has been reset with the new password."
}
```

**Error Responses:**

*400 Bad Request - Invalid/Expired token:*
```json
{
  "token": ["Invalid value"]
}
```

*400 Bad Request - Invalid uid:*
```json
{
  "uid": ["Invalid value"]
}
```

*400 Bad Request - Password mismatch:*
```json
{
  "new_password2": ["The two password fields didn't match."]
}
```

**Process:**
- Validates uid and token
- Checks token expiry (1 hour)
- Updates user password
- Invalidates the reset token
- User must login with new password

---

## Two-Factor Authentication (2FA)

### Overview

2FA adds an extra security layer using Time-based One-Time Passwords (TOTP) compatible with:
- Google Authenticator
- Microsoft Authenticator
- Authy
- 1Password
- Any TOTP-compatible app

### 2FA Flow

```
1. Setup 2FA → Scan QR Code → Verify Code → Receive Backup Codes
2. Login → Enter Password → Enter 2FA Code → Access Granted
```

---

### 1. Setup 2FA - Generate QR Code

Initiate 2FA setup and receive QR code.

**Endpoint:** `GET /api/accounts/2fa/setup/`

**Authentication:** Required

**Success Response (200 OK):**
```json
{
  "qr_code": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",
  "secret": "JBSWY3DPEHPK3PXP",
  "device_id": 1
}
```

**Response Fields:**
- `qr_code`: Base64-encoded PNG image for scanning
- `secret`: Manual entry key if QR scan fails
- `device_id`: Device identifier for verification step

**Error Response:**

*400 Bad Request - Already enabled:*
```json
{
  "detail": "2FA is already enabled"
}
```

**Usage Instructions:**
1. Open authenticator app
2. Choose "Scan QR Code" or "Enter manually"
3. Scan the QR code OR enter the secret key
4. Authenticator will start generating 6-digit codes
5. Proceed to verification step

**QR Code Format:**
```
otpauth://totp/Mini%20E-Com:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=Mini+E-Com
```

---

### 2. Verify 2FA Setup

Verify TOTP code and complete 2FA setup.

**Endpoint:** `POST /api/accounts/2fa/setup/verify/`

**Authentication:** Required

**Request Body:**
```json
{
  "token": "123456",
  "device_id": 1
}
```

**Success Response (200 OK):**
```json
{
  "detail": "2FA enabled successfully",
  "backup_codes": [
    "a1b2c3d4",
    "e5f6g7h8",
    "i9j0k1l2",
    "m3n4o5p6",
    "q7r8s9t0",
    "u1v2w3x4",
    "y5z6a7b8",
    "c9d0e1f2",
    "g3h4i5j6",
    "k7l8m9n0"
  ]
}
```

**Error Responses:**

*400 Bad Request - Missing token:*
```json
{
  "error": "Token is required"
}
```

*400 Bad Request - Invalid format:*
```json
{
  "error": "Token must be a 6-digit code"
}
```

*400 Bad Request - Invalid device:*
```json
{
  "error": "Invalid device"
}
```

*400 Bad Request - Invalid code:*
```json
{
  "error": "Invalid token"
}
```

**Process:**
- Verifies the 6-digit TOTP code
- Confirms the TOTP device
- Generates 10 backup codes
- Returns backup codes (SAVE THESE!)

**Backup Codes:**
- 10 single-use codes
- 8 characters each (alphanumeric)
- Use when authenticator unavailable
- Generate new codes after using one

**Important Security Notes:**
- ⚠️ Save backup codes in a secure location
- ⚠️ Backup codes shown only once
- ⚠️ Each backup code is single-use
- ⚠️ Losing access to both authenticator and backup codes = account lockout

---

### 3. Verify 2FA During Login

Handled automatically by login endpoint when 2FA is enabled.

See [Login with 2FA Verification](#4-login-with-2fa-verification) section above.

---

### 4. Check 2FA Status

Check if user has 2FA enabled.

**Endpoint:** `GET /api/accounts/2fa/status/`

**Authentication:** Required

**Success Response (200 OK):**
```json
{
  "2fa_enabled": true,
  "devices": 1
}
```

**Response Fields:**
- `2fa_enabled`: Boolean indicating if 2FA is active
- `devices`: Number of confirmed TOTP devices

**Use Cases:**
- Display 2FA status in user settings
- Conditional UI rendering
- Security dashboard

---

### 5. Disable 2FA

Disable two-factor authentication.

**Endpoint:** `POST /api/accounts/2fa/disable/`

**Authentication:** Required

**Request Body:**
```json
{
  "password": "SecurePass123!"
}
```

**Success Response (200 OK):**
```json
{
  "detail": "2FA disabled successfully"
}
```

**Error Response:**

*400 Bad Request - Wrong password:*
```json
{
  "error": "Invalid password"
}
```

**Process:**
- Requires password confirmation for security
- Deletes all TOTP devices
- Deletes all backup codes
- User can login with just password

**Security Considerations:**
- Requires password re-verification
- Sends notification email (recommended to implement)
- Log the action for audit trail

---

## Social Authentication

### Overview

Authenticate using Google or Facebook accounts with optional 2FA integration.

### Supported Providers
- ✅ Google OAuth 2.0
- ✅ Facebook OAuth 2.0

### Social Auth Flow

```
Standard Flow:
1. Frontend initiates OAuth → 2. Provider authentication → 3. Exchange token → 4. Login complete

With 2FA:
1. Frontend initiates OAuth → 2. Provider authentication → 3. Exchange token → 
4. 2FA challenge → 5. Verify code → 6. Login complete
```

---

### 1. Google Login

Authenticate using Google account.

**Endpoint:** `POST /api/auth/google/`

**Request Body:**
```json
{
  "access_token": "ya29.a0AfH6SMBx..."
}
```

**Success Response (200 OK) - Without 2FA:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "pk": 1,
    "email": "user@gmail.com",
    "username": "user_gmail_com",
    "first_name": "John",
    "last_name": "Doe",
    "display_name": "John Doe",
    "phone_number": null,
    "phone_verified": false,
    "date_of_birth": null,
    "profile_picture": "https://lh3.googleusercontent.com/...",
    "social_accounts": [
      {
        "provider": "google",
        "uid": "1234567890",
        "date_joined": "2025-01-15T10:30:00Z"
      }
    ],
    "has_2fa": false
  }
}
```

**Challenge Response (202 Accepted) - With 2FA:**
```json
{
  "detail": "2FA verification required",
  "requires_2fa": true,
  "user_id": 1,
  "provider": "google"
}
```

**Error Responses:**

*400 Bad Request - Invalid token:*
```json
{
  "detail": "Google token validation failed",
  "error": "Invalid access token"
}
```

*400 Bad Request - Token exchange failed:*
```json
{
  "detail": "Google token validation failed",
  "error": "Failed to exchange token"
}
```

**Frontend Implementation (React Example):**
```javascript
// 1. Initiate Google OAuth
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';

function LoginButton() {
  const handleSuccess = async (credentialResponse) => {
    // 2. Send token to backend
    const response = await fetch('http://localhost:8000/api/auth/google/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        access_token: credentialResponse.credential
      })
    });

    const data = await response.json();

    if (response.status === 202 && data.requires_2fa) {
      // 3. Show 2FA modal
      show2FAModal(data.user_id, 'google');
    } else {
      // 4. Save tokens and redirect
      saveTokens(data.access, data.refresh);
      redirect('/dashboard');
    }
  };

  return (
    <GoogleOAuthProvider clientId="YOUR_GOOGLE_CLIENT_ID">
      <GoogleLogin onSuccess={handleSuccess} onError={() => alert('Login Failed')} />
    </GoogleOAuthProvider>
  );
}
```

**Account Linking:**
- If email exists: Links Google account to existing user
- If new email: Creates new user automatically
- No email verification required for social accounts
- Profile picture automatically imported from Google

---

### 2. Facebook Login

Authenticate using Facebook account.

**Endpoint:** `POST /api/auth/facebook/`

**Request Body:**
```json
{
  "access_token": "EAAFz..."
}
```

**Responses:** Same format as Google Login

**Facebook Permissions Required:**
- `email` (required)
- `public_profile` (required)

**Frontend Implementation (React Example):**
```javascript
import FacebookLogin from 'react-facebook-login';

function FacebookLoginButton() {
  const responseFacebook = async (response) => {
    if (response.accessToken) {
      const backendResponse = await fetch('http://localhost:8000/api/auth/facebook/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          access_token: response.accessToken
        })
      });

      const data = await backendResponse.json();

      if (backendResponse.status === 202 && data.requires_2fa) {
        show2FAModal(data.user_id, 'facebook');
      } else {
        saveTokens(data.access, data.refresh);
        redirect('/dashboard');
      }
    }
  };

  return (
    <FacebookLogin
      appId="YOUR_FACEBOOK_APP_ID"
      autoLoad={false}
      fields="name,email,picture"
      callback={responseFacebook}
    />
  );
}
```

---

### 3. Social Login with 2FA

Complete social login when 2FA is enabled.

**Endpoint:** `POST /api/auth/google/` or `POST /api/auth/facebook/`

**Request Body:**
```json
{
  "user_id": 1,
  "otp_verified": true,
  "token": "123456"
}
```

**Success Response (200 OK) - TOTP:**
```json
{
  "detail": "Google login successful",
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "pk": 1,
    "email": "user@gmail.com",
    "username": "user_gmail_com",
    "first_name": "John",
    "last_name": "Doe",
    "display_name": "John Doe",
    "phone_number": null,
    "phone_verified": false,
    "date_of_birth": null,
    "profile_picture": "https://lh3.googleusercontent.com/...",
    "social_accounts": [
      {
        "provider": "google",
        "uid": "1234567890",
        "date_joined": "2025-01-15T10:30:00Z"
      }
    ],
    "has_2fa": true
  }
}
```

**Success Response (200 OK) - Backup Code:**
```json
{
  "detail": "Facebook login successful",
  "warning": "Backup code used. Please generate new backup codes",
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": { ... }
}
```

**Error Responses:**

*400 Bad Request - Missing data:*
```json
{
  "detail": "User ID and token required"
}
```

*400 Bad Request - Session mismatch:*
```json
{
  "detail": "Invalid session or user ID mismatch"
}
```

*400 Bad Request - Invalid code:*
```json
{
  "detail": "Invalid 2FA token."
}
```

**Session Management:**
- Social login creates temporary session during OAuth
- Session cleared after successful authentication
- 2FA verification must happen in same session
- Session timeout: 5 minutes

---

## Phone Verification

### Overview

Optional phone verification using SMS codes with rate limiting and Redis caching.

### Phone Verification Flow

```
1. Add Phone → 2. Request Code → 3. Receive SMS → 4. Verify Code → 5. Phone Verified
```

### Configuration

From [`settings.py`](mini_ecom/settings.py):
```python
PHONE_VERIFICATION = {
    'CODE_LENGTH': 6,                              # 6-digit codes
    'CODE_EXPIRY_MINUTES': 10,                     # Codes expire in 10 minutes
    'MAX_ATTEMPTS': 5,                             # Max verification attempts
    'RATE_LIMIT_CODES_PER_HOUR': 3,               # Max 3 codes per hour
    'RATE_LIMIT_VERIFICATIONS_PER_MINUTE': 5,     # Max 5 verifications per minute
    'USE_REDIS': True,                             # Use Redis for caching
    'REDIS_KEY_PREFIX': 'phone_verify'             # Redis key prefix
}
```

---

### 1. Send Verification Code

Request SMS verification code for phone number.

**Endpoint:** `POST /api/accounts/phone/send-code/`

**Authentication:** Required

**Throttling:** 3 codes per hour per user

**Request Body:**
```json
{
  "phone_number": "+2348012345678"
}
```

**Phone Number Format:**
- Must be in E.164 international format
- Example: `+2348012345678` (Nigeria)
- Example: `+14155552671` (US)
- Example: `+447911123456` (UK)

**Success Response (200 OK):**
```json
{
  "detail": "Verification code sent successfully",
  "phone_number": "+2348012345678",
  "expires_in_minutes": 10
}
```

**Error Responses:**

*400 Bad Request - Invalid format:*
```json
{
  "detail": "Invalid phone number.",
  "errors": {
    "phone_number": ["Enter a valid phone number."]
  }
}
```

*400 Bad Request - Already verified:*
```json
{
  "detail": "Invalid phone number.",
  "errors": {
    "phone_number": ["This phone number is already verified"]
  }
}
```

*429 Too Many Requests:*
```json
{
  "detail": "Too many code requests. Please wait before requesting another code.",
  "type": "rate_limited",
  "retry_after": 1800
}
```

*500 Internal Server Error - SMS failed:*
```json
{
  "detail": "Failed to send verification code. Please try again later.",
  "type": "sms_send_failed"
}
```

**Process:**
- Validates phone number format
- Checks rate limits
- Generates 6-digit random code
- Sends SMS via Twilio (or logs to console in development)
- Stores code in database with expiry
- Updates user's phone number (unverified)

**Development Mode:**
```bash
# SMS codes are logged to console instead of sent
# Look for: "SMS Code: 123456 for +2348012345678"
```

---

### 2. Verify Phone Number

Verify phone number using SMS code.

**Endpoint:** `POST /api/accounts/phone/verify/`

**Authentication:** Required

**Throttling:** 5 verifications per minute per user

**Request Body:**
```json
{
  "phone_number": "+2348012345678",
  "code": "123456"
}
```

**Success Response (200 OK):**
```json
{
  "detail": "Phone number verified successfully.",
  "phone_number": "+2348012345678",
  "verified": true
}
```

**Error Responses:**

*400 Bad Request - Invalid data:*
```json
{
  "detail": "Invalid verification data.",
  "errors": {
    "code": ["This field is required."]
  }
}
```

*400 Bad Request - Invalid/Expired code:*
```json
{
  "detail": "Invalid or expired verification code",
  "type": "invalid_code"
}
```

*400 Bad Request - Too many attempts:*
```json
{
  "detail": "Maximum verification attempts exceeded. Please request a new code.",
  "type": "invalid_code"
}
```

**Process:**
- Validates code format (6 digits)
- Checks code against database
- Verifies code not expired (10 minutes)
- Checks attempt count (max 5)
- Marks phone as verified
- Invalidates the verification code

**Attempt Tracking:**
- Each failed verification increments attempt counter
- After 5 failed attempts, must request new code
- Counter resets when new code is requested
- Prevents brute force attacks

---

### 3. Check Phone Status

Get current phone verification status.

**Endpoint:** `GET /api/accounts/phone/status/`

**Authentication:** Required

**Success Response (200 OK):**
```json
{
  "phone_number": "+2348012345678",
  "verified": true,
  "can_request_code": true,
  "retry_after": 0,
  "max_attempts": 5,
  "code_expires_in_minutes": 10
}
```

**Response Fields:**
- `phone_number`: Current phone number or null
- `verified`: Boolean verification status
- `can_request_code`: Whether user can request new code
- `retry_after`: Seconds to wait before next code request (0 if allowed)
- `max_attempts`: Maximum verification attempts per code
- `code_expires_in_minutes`: Code validity duration

**Use Cases:**
- Display verification status in UI
- Show countdown timer for retry
- Disable/enable "Send Code" button
- Display verification badge

---

### 4. Update Phone Number

Update user's phone number (requires re-verification).

**Endpoint:** `PUT/PATCH /api/accounts/phone/update/`

**Authentication:** Required

**Request Body:**
```json
{
  "phone_number": "+2348087654321"
}
```

**Success Response (200 OK):**
```json
{
  "detail": "Phone number updated. Please verified your new phone number.",
  "phone_number": "+2348087654321",
  "verified": false
}
```

**Error Responses:**

*400 Bad Request - Invalid format:*
```json
{
  "detail": "Invalid phone number.",
  "errors": {
    "phone_number": ["Enter a valid phone number."]
  }
}
```

*400 Bad Request - Already taken:*
```json
{
  "detail": "Invalid phone number.",
  "errors": {
    "phone_number": ["This phone number is already verified by another user"]
  }
}
```

**Process:**
- Updates phone number
- Marks as unverified
- User must request new verification code
- Old verification codes are invalidated

**Important Notes:**
- Changing phone number resets verification status
- Must complete verification flow for new number
- Old phone number is immediately replaced

---

### 5. Remove Phone Number

Remove phone number from account.

**Endpoint:** `DELETE /api/accounts/phone/remove/`

**Authentication:** Required

**Success Response (200 OK):**
```json
{
  "detail": "Phone number removed successfully."
}
```

**Process:**
- Removes phone number
- Clears verification status
- Deletes pending verification codes
- User can add new phone number anytime

---

## Email Management

### 1. Change Email Address

Change account email (requires password and re-verification).

**Endpoint:** `POST /api/accounts/email/change/`

**Authentication:** Required

**Request Body:**
```json
{
  "new_email": "newemail@example.com",
  "password": "SecurePass123!"
}
```

**Success Response (200 OK):**
```json
{
  "detail": "Email change successful. Please verify your new email address.",
  "old_email": "user@example.com",
  "new_email": "newemail@example.com",
  "verification_sent": true
}
```

**Error Responses:**

*400 Bad Request - Invalid password:*
```json
{
  "password": ["Invalid password"]
}
```

*400 Bad Request - Email exists:*
```json
{
  "new_email": ["A user is already registered with this email address."]
}
```

*400 Bad Request - Same email:*
```json
{
  "new_email": ["New email must be different from current email"]
}
```

**Process:**
1. Validates password
2. Checks new email availability
3. Deletes old EmailAddress entry
4. Updates user email
5. Marks account as inactive
6. Creates new EmailAddress entry (unverified)
7. Sends verification email to new address

**Important Security Notes:**
- ⚠️ Account becomes inactive until new email is verified
- ⚠️ User is logged out automatically
- ⚠️ Verification link sent to NEW email address
- ⚠️ Old email receives notification (recommended to implement)
- ⚠️ Cannot login until verification complete

**User Experience Flow:**
```
1. Request email change with password
2. Account deactivated
3. Verification email sent to NEW address
4. User clicks link in NEW email
5. Account reactivated
6. User must login again
```

---

### 2. Resend Verification Email

Resend email verification link for pending verification.

**Endpoint:** `POST /api/accounts/email/resend-verification/`

**Authentication:** Required

**Request Body:**
```json
{
  "email": "newemail@example.com"
}
```

**Success Response (200 OK):**
```json
{
  "detail": "Verification email sent.",
  "email": "newemail@example.com"
}
```

**Error Responses:**

*400 Bad Request - Already verified:*
```json
{
  "detail": "Your email is already verified."
}
```

*200 OK - Email not found (security):*
```json
{
  "detail": "If this email exist, Verification email sent"
}
```

**Process:**
- Only works for inactive accounts with pending verification
- Generates new verification link
- Extends verification deadline
- Previous links remain valid

**Use Cases:**
- Email didn't arrive
- Verification link expired
- User changed email and needs new link

---

## Error Handling

### Standard Error Format

All error responses follow consistent format:

**Single Error:**
```json
{
  "detail": "Error message describing the issue"
}
```

**Field Validation Errors:**
```json
{
  "field_name": ["Error message for this field"],
  "another_field": ["Another error message"]
}
```

**Multiple Errors:**
```json
{
  "detail": "Operation failed",
  "errors": {
    "email": ["This field is required."],
    "password": ["This field is required."]
  }
}
```

### HTTP Status Codes

| Code | Meaning | Use Case |
|------|---------|----------|
| 200 | OK | Successful GET, PUT, PATCH, DELETE |
| 201 | Created | Successful POST (creation) |
| 202 | Accepted | 2FA challenge issued |
| 400 | Bad Request | Validation errors, invalid data |
| 401 | Unauthorized | Authentication required/failed |
| 403 | Forbidden | Insufficient permissions, account inactive |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server-side error |

### Common Error Scenarios

#### 1. Authentication Errors

*Missing Token:*
```json
{
  "detail": "Authentication credentials were not provided."
}
```

*Invalid Token:*
```json
{
  "detail": "Given token not valid for any token type",
  "code": "token_not_valid"
}
```

*Expired Token:*
```json
{
  "detail": "Token is invalid or expired",
  "code": "token_not_valid"
}
```

#### 2. Validation Errors

*Required Field:*
```json
{
  "field_name": ["This field is required."]
}
```

*Invalid Format:*
```json
{
  "email": ["Enter a valid email address."]
}
```

*Unique Constraint:*
```json
{
  "username": ["A user with that username already exists."]
}
```

#### 3. Rate Limit Errors

```json
{
  "detail": "Request was throttled. Expected available in 3600 seconds.",
  "type": "rate_limited",
  "retry_after": 3600
}
```

#### 4. Permission Errors

```json
{
  "detail": "You do not have permission to perform this action."
}
```

### Error Handling Best Practices

**Frontend Example (React):**
```javascript
async function handleLogin(email, password) {
  try {
    const response = await fetch('/api/auth/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    const data = await response.json();

    // Handle different status codes
    switch (response.status) {
      case 200:
        // Success - save tokens
        saveTokens(data.access, data.refresh);
        redirect('/dashboard');
        break;

      case 202:
        // 2FA required
        show2FAModal(data.user_id);
        break;

      case 400:
        // Validation errors
        if (data.non_field_errors) {
          showError(data.non_field_errors[0]);
        } else {
          // Field-specific errors
          Object.keys(data).forEach(field => {
            showFieldError(field, data[field][0]);
          });
        }
        break;

      case 403:
        // Account inactive
        if (data.verification_required) {
          showEmailVerificationPrompt(data.email);
        } else {
          showError(data.detail);
        }
        break;

      case 429:
        // Rate limited
        const waitTime = Math.ceil(data.retry_after / 60);
        showError(`Too many attempts. Try again in ${waitTime} minutes.`);
        break;

      default:
        showError('An unexpected error occurred. Please try again.');
    }
  } catch (error) {
    console.error('Login error:', error);
    showError('Network error. Please check your connection.');
  }
}
```

---

## Rate Limiting

### Overview

Rate limiting protects the API from abuse and ensures fair usage.

### Global Rate Limits

From [`settings.py`](mini_ecom/settings.py):

| Endpoint Type | Limit | Scope |
|--------------|-------|-------|
| Anonymous requests | 100/day | Per IP |
| Authenticated requests | 1000/day | Per user |

### Endpoint-Specific Limits

| Endpoint | Limit | Scope | Throttle Class |
|----------|-------|-------|----------------|
| `/api/auth/register/` | 10/day | Per IP | [`SignupRateThrottle`](accounts/throttle.py) |
| `/api/auth/login/` | 5/minute | Per IP | [`LoginRateThrottle`](accounts/throttle.py) |
| `/api/auth/password/reset/` | 5/hour | Per IP | [`PasswordResetRateThrottle`](accounts/throttle.py) |
| `/api/accounts/phone/send-code/` | 3/hour | Per user | Custom in view |
| `/api/accounts/phone/verify/` | 5/minute | Per user | Custom in view |

### Rate Limit Headers

Responses include rate limit information:

```http
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1642780800
```

### Rate Limit Exceeded Response

```json
{
  "detail": "Request was throttled. Expected available in 300 seconds.",
  "retry_after": 300
}
```

### Handling Rate Limits

**Frontend Example:**
```javascript
async function makeRequest(url, options) {
  const response = await fetch(url, options);

  if (response.status === 429) {
    const data = await response.json();
    const retryAfter = data.retry_after || 60;
    
    // Show user-friendly message
    const minutes = Math.ceil(retryAfter / 60);
    showNotification(
      `Too many requests. Please wait ${minutes} minute(s) and try again.`,
      'warning'
    );

    // Optionally implement automatic retry
    setTimeout(() => {
      makeRequest(url, options);
    }, retryAfter * 1000);

    return null;
  }

  return response;
}
```

### Redis Caching for Phone Verification

Phone verification uses Redis for efficient rate limiting:

```python
# Cache key format
phone_verify:{phone_number}:code_sent_count
phone_verify:{phone_number}:last_code_time
phone_verify:{phone_number}:verification_attempts
```

**Cache Timeouts:**
- Code sent count: 1 hour
- Last code time: 1 hour
- Verification attempts: 10 minutes (code expiry)

---

## Security Best Practices

### 1. Token Management

**✅ Do:**
- Store tokens in httpOnly cookies (web)
- Use secure storage (Keychain/Keystore for mobile)
- Implement token refresh before expiry
- Clear tokens on logout
- Use HTTPS in production

**❌ Don't:**
- Store tokens in localStorage (XSS vulnerable)
- Expose tokens in URLs or logs
- Share tokens between users
- Store tokens in plain text

**Token Storage Example (React):**
```javascript
// Good: Use httpOnly cookies (handled by backend)
// Tokens automatically included in requests

// Alternative for mobile: Secure storage
import * as SecureStore from 'expo-secure-store';

async function saveTokens(access, refresh) {
  await SecureStore.setItemAsync('access_token', access);
  await SecureStore.setItemAsync('refresh_token', refresh);
}

async function getAccessToken() {
  return await SecureStore.getItemAsync('access_token');
}
```

### 2. 2FA Implementation

**✅ Best Practices:**
- Always save backup codes securely
- Display backup codes only once
- Prompt users to store codes offline
- Generate new backup codes after use
- Log 2FA enable/disable events
- Notify users via email

**❌ Security Risks:**
- Don't email backup codes
- Don't store backup codes in plain text
- Don't allow unlimited verification attempts
- Don't skip password confirmation for 2FA disable

### 3. Phone Verification

**✅ Best Practices:**
- Validate phone numbers on client-side
- Display clear instructions
- Show retry countdown
- Log verification attempts
- Implement SMS rate limiting
- Use reputable SMS providers (Twilio)

**❌ Security Risks:**
- Don't allow unlimited code requests
- Don't send codes to unvalidated numbers
- Don't expose verification codes in logs
- Don't reuse verification codes

### 4. Password Security

**✅ Best Practices:**
- Enforce strong password requirements
- Use Django's built-in password validators
- Implement account lockout after failed attempts
- Log password changes
- Notify users of password changes
- Require old password for changes

**Password Requirements:**
- Minimum 8 characters
- Not similar to user attributes
- Not too common (checked against common passwords list)
- Not entirely numeric

### 5. Social Authentication

**✅ Best Practices:**
- Validate provider tokens server-side
- Don't trust client-supplied data
- Link social accounts properly
- Implement 2FA for social logins
- Log social authentication events

**❌ Security Risks:**
- Don't skip token validation
- Don't expose provider credentials
- Don't allow account hijacking via social login

### 6. Email Security

**✅ Best Practices:**
- Use HMAC for verification links
- Set reasonable expiry times
- Require password for email changes
- Notify on email changes
- Implement anti-phishing measures

**Email Verification Token:**
```python
# From settings.py
ACCOUNT_EMAIL_CONFIRMATION_HMAC = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
```

### 7. API Security Checklist

- ✅ Always use HTTPS in production
- ✅ Implement CSRF protection
- ✅ Enable CORS properly
- ✅ Validate all inputs
- ✅ Sanitize error messages
- ✅ Log security events
- ✅ Monitor for suspicious activity
- ✅ Keep dependencies updated
- ✅ Use environment variables for secrets
- ✅ Implement rate limiting
- ✅ Enable HSTS headers
- ✅ Set secure cookie flags

**Production Settings Example:**
```python
# settings.py
DEBUG = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
```

### 8. Monitoring and Logging

**✅ Log These Events:**
- Login attempts (success/failure)
- 2FA enable/disable
- Password changes
- Email changes
- Social account linking
- Phone verification attempts
- Rate limit violations
- Suspicious activity

**Example Logging:**
```python
import logging
logger = logging.getLogger(__name__)

# Login success
logger.info(
    f"User {user.id} logged in successfully",
    extra={
        'user_id': user.id,
        'ip_address': request.META.get('REMOTE_ADDR'),
        'user_agent': request.META.get('HTTP_USER_AGENT')
    }
)

# Failed login
logger.warning(
    f"Failed login attempt for {email}",
    extra={
        'email': email,
        'ip_address': request.META.get('REMOTE_ADDR')
    }
)

# 2FA enabled
logger.info(
    f"2FA enabled for user {user.id}",
    extra={'user_id': user.id}
)
```

### 9. Data Protection

**✅ GDPR Compliance:**
- Allow users to export their data
- Implement account deletion
- Don't store unnecessary personal data
- Encrypt sensitive data at rest
- Implement data retention policies

**❌ Privacy Risks:**
- Don't log passwords or tokens
- Don't expose PII in error messages
- Don't share data without consent
- Don't keep deleted user data

---

## Testing

### Using Postman

See [POSTMAN_SETUP.md](docs/POSTMAN_SETUP.md) for complete Postman collection.

### Using cURL

**Register:**
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password1": "TestPass123!",
    "password2": "TestPass123!",
    "phone_number": "+2348012345678"
  }'
```

**Login:**
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!"
  }'
```

**Authenticated Request:**
```bash
curl -X GET http://localhost:8000/api/accounts/profile/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

---

## Support

### Documentation
- API Documentation: This file
- Setup Guide: [SETUP_GUIDE.md](docs/SETUP_GUIDE.md)
- Postman Collection: [POSTMAN_SETUP.md](docs/POSTMAN_SETUP.md)

### Django Allauth Documentation
- Official Docs: https://docs.allauth.org/en/latest/
- Configuration: https://docs.allauth.org/en/latest/account/configuration.html
- Social Providers: https://docs.allauth.org/en/latest/socialaccount/providers/index.html

### Contact
- Email: support@mini-ecom.com
- GitHub Issues: [repository-url]/issues

---

**Last Updated:** January 2025  
**API Version:** 1.0  
