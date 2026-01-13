from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from core.models import Storage, User
from v1.auth.dependencies import get_current_user, get_db_session


sync_router = APIRouter(prefix="/sync", tags=["sync"])


# Response models
class StorageChange(BaseModel):
    id: str
    username_data: bytes
    password_data: bytes
    domains: bytes
    notes: bytes
    created_at: datetime
    updated: datetime
    deleted_at: Optional[datetime]


class SyncChangesResponse(BaseModel):
    changes: List[StorageChange]
    next_cursor: Optional[str]
    has_more: bool


# Request models for push
class StorageCreateUpdate(BaseModel):
    id: str
    username_data: bytes
    password_data: bytes
    domains: bytes
    notes: bytes
    updated: datetime  # Client's timestamp


class StorageDelete(BaseModel):
    id: str
    updated: datetime  # Client's timestamp for conflict detection


class SyncPushRequest(BaseModel):
    creates: List[StorageCreateUpdate] = []
    updates: List[StorageCreateUpdate] = []
    deletes: List[StorageDelete] = []


class ConflictItem(BaseModel):
    id: str
    client_updated: datetime
    server_updated: datetime
    reason: str


class SyncPushResponse(BaseModel):
    applied: int
    conflicts: List[ConflictItem]


@sync_router.get("/changes", response_model=SyncChangesResponse)
async def get_changes(
    since: Optional[datetime] = None,
    limit: int = 100,
    cursor: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Get storage changes since a timestamp with cursor-based pagination.

    - **since**: ISO timestamp to fetch changes after (optional, fetches all if not provided)
    - **limit**: Max number of items to return (default 100, max 1000)
    - **cursor**: Pagination cursor from previous response (format: "timestamp_id")
    """
    if limit > 1000:
        limit = 1000

    query = select(Storage).where(Storage.user_id == current_user.id)

    # Apply since filter
    if since:
        query = query.where(Storage.updated > since)

    # Apply cursor-based pagination
    if cursor:
        try:
            cursor_parts = cursor.split("_", 1)
            cursor_timestamp = datetime.fromisoformat(cursor_parts[0])
            cursor_id = cursor_parts[1]

            query = query.where(
                (Storage.updated > cursor_timestamp)
                | ((Storage.updated == cursor_timestamp) & (Storage.id > cursor_id))
            )
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor format"
            )

    # Order by updated, then id for stable pagination
    query = query.order_by(Storage.updated, Storage.id).limit(limit + 1)

    results = db.exec(query).all()

    has_more = len(results) > limit
    items = results[:limit]

    next_cursor = None
    if has_more and items:
        last_item = items[-1]
        next_cursor = f"{last_item.updated.isoformat()}_{last_item.id}"

    changes = [
        StorageChange(
            id=item.id,
            username_data=item.username_data,
            password_data=item.password_data,
            domains=item.domains,
            notes=item.notes,
            created_at=item.created_at,
            updated=item.updated,
            deleted_at=item.deleted_at,
        )
        for item in items
    ]

    return SyncChangesResponse(
        changes=changes,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@sync_router.post("/push", response_model=SyncPushResponse)
async def push_changes(
    payload: SyncPushRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Push changes to server with last-write-wins conflict resolution.

    Server timestamp always wins. If server has a newer timestamp, operation is rejected
    and returned in conflicts array for client to handle.
    """
    applied_count = 0
    conflicts: List[ConflictItem] = []

    # Process creates
    for create_item in payload.creates:
        existing = db.exec(
            select(Storage).where(
                Storage.id == create_item.id, Storage.user_id == current_user.id
            )
        ).first()

        if existing:
            # Item already exists - check for conflict
            if existing.updated > create_item.updated:
                conflicts.append(
                    ConflictItem(
                        id=create_item.id,
                        client_updated=create_item.updated,
                        server_updated=existing.updated,
                        reason="Server has newer version",
                    )
                )
                continue

        # Create new or overwrite (last-write-wins)
        server_time = datetime.now()
        new_storage = Storage(
            id=create_item.id,
            user_id=current_user.id,
            username_data=create_item.username_data,
            password_data=create_item.password_data,
            domains=create_item.domains,
            notes=create_item.notes,
            created_at=server_time if not existing else existing.created_at,
            updated=server_time,
            deleted_at=None,
        )

        if existing:
            db.delete(existing)

        db.add(new_storage)
        applied_count += 1

    # Process updates
    for update_item in payload.updates:
        existing = db.exec(
            select(Storage).where(
                Storage.id == update_item.id, Storage.user_id == current_user.id
            )
        ).first()

        if not existing:
            conflicts.append(
                ConflictItem(
                    id=update_item.id,
                    client_updated=update_item.updated,
                    server_updated=datetime.min,
                    reason="Item not found on server",
                )
            )
            continue

        if existing.updated > update_item.updated:
            conflicts.append(
                ConflictItem(
                    id=update_item.id,
                    client_updated=update_item.updated,
                    server_updated=existing.updated,
                    reason="Server has newer version",
                )
            )
            continue

        # Apply update with server timestamp
        server_time = datetime.now()
        existing.username_data = update_item.username_data
        existing.password_data = update_item.password_data
        existing.domains = update_item.domains
        existing.notes = update_item.notes
        existing.updated = server_time
        existing.deleted_at = None  # Undelete if was deleted

        db.add(existing)
        applied_count += 1

    # Process deletes (soft delete)
    for delete_item in payload.deletes:
        existing = db.exec(
            select(Storage).where(
                Storage.id == delete_item.id, Storage.user_id == current_user.id
            )
        ).first()

        if not existing:
            # Already deleted or doesn't exist - not a conflict, just skip
            continue

        if existing.updated > delete_item.updated:
            conflicts.append(
                ConflictItem(
                    id=delete_item.id,
                    client_updated=delete_item.updated,
                    server_updated=existing.updated,
                    reason="Server has newer version",
                )
            )
            continue

        # Apply soft delete with server timestamp
        server_time = datetime.now()
        existing.deleted_at = server_time
        existing.updated = server_time

        db.add(existing)
        applied_count += 1

    db.commit()

    return SyncPushResponse(
        applied=applied_count,
        conflicts=conflicts,
    )
