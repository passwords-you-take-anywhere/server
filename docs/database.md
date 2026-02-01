# Database

PYTA uses PostgreSQL with SQLModel.

## Engine creation

- Connection URLs are constructed safely using URL encoding
- Engines are cached using LRU caching
- Connection health is ensured with `pool_pre_ping`

## Models

### Auth

Stores login credentials.

- email (unique)
- password (hashed)
- role_id

### User

Stores encryption keys and links to auth.

- encryption_key (binary)
- one-to-one with Auth

### Session

Represents a login session.

- HTTP-only cookie based
- Stored server-side

### Storage

Encrypted credential storage.

- username_data
- password_data
- domains
- notes
