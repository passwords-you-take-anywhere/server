# Security Considerations

## Implemented protections

- Password hashing (PBKDF2)
- HTTP-only cookies
- Encrypted storage fields
- Server-side sessions
- Environment-based secrets

## Recommendations

- Enable HTTPS in production
- Rotate encryption keys carefully
- Use a secrets manager for production
- Add rate limiting to auth endpoints
