# Authentication

Authentication is session-based using cookies.

## Flow

1. User logs in or registers
2. Password is hashed with PBKDF2
3. Session record is created
4. Session ID is stored in an HTTP-only cookie

## Cookies

- `session_id`
- HTTP-only
- Secure in production
- SameSite=Lax

## Session handling

- Sessions are stored in the database
- Session ID is sent as an HTTP-only cookie
- Cookies are marked secure in non-debug mode

