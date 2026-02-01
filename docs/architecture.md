# Architecture Overview

PYTA follows a modular backend architecture.

## Core Modules

| Module | Responsibility |
|------|---------------|
| `auth_router.py` | Authentication endpoints |
| `models.py` | Database models |
| `db.py` | Database engine & sessions |
| `passwords.py` | Password hashing |
| `settings.py` | Environment configuration |

## Request Flow

1. Client sends request
2. FastAPI route handles logic
3. Database session is injected
4. SQLModel performs queries
5. Response returned with cookie/session
