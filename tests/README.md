# Testing

## Setup

Install test dependencies:
```bash
uv sync --group test
```

## Running Tests

Run all tests:
```bash
uv run pytest tests/
```

Run with verbose output:
```bash
uv run pytest tests/ -v
```

Run specific test file:
```bash
uv run pytest tests/test_sync_router.py
```

Run specific test:
```bash
uv run pytest tests/test_sync_router.py::TestSyncChangesEndpoint::test_get_changes_with_pagination
```

Run with coverage:
```bash
uv run pytest tests/ --cov=src --cov-report=html
```

## Test Structure

- `tests/conftest.py` - Shared fixtures and test configuration
  - In-memory SQLite database for fast tests
  - Test user and session fixtures
  - FastAPI test client setup
  
- `tests/test_auth_dependency.py` - Authentication tests (5 tests)
  - Session validation
  - Cookie vs header precedence
  - Error handling
  
- `tests/test_sync_router.py` - Sync endpoint tests (19 tests)
  - **GET /sync/changes** (9 tests)
    - Authentication requirements
    - Initial sync (all data)
    - Incremental sync with timestamps
    - Cursor-based pagination
    - Soft-deleted items inclusion
    - User isolation
    - Response structure validation
    
  - **POST /sync/push** (10 tests)
    - Create new items
    - Update existing items
    - Soft delete items
    - Last-write-wins conflict resolution
    - Mixed operations (create/update/delete)
    - Undelete on update
    - User isolation
    - Error handling

## Test Coverage

Total: **24 tests** covering:
- ✅ Authentication with UUIDv4 sessions
- ✅ GET /sync/changes endpoint
- ✅ POST /sync/push endpoint
- ✅ Pagination and cursors
- ✅ Conflict resolution (last-write-wins)
- ✅ Soft deletes
- ✅ User data isolation
- ✅ Error cases and edge conditions
