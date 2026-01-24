from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from core.models import Domain, Storage, StorageDomain, User
from v1.auth.dependencies import get_current_user, get_db_session

sync_router = APIRouter(prefix="/sync", tags=["sync"])


# Response models
class StorageChange(BaseModel):
    id: str
    username_data: bytes
    password_data: bytes
    domains: list[bytes]
    notes: bytes
    created_at: datetime
    updated: datetime
    deleted_at: datetime | None


class SyncChangesResponse(BaseModel):
    changes: list[StorageChange]
    next_cursor: str | None
    has_more: bool


# Request models for push
class StorageCreateUpdate(BaseModel):
    id: str
    username_data: bytes
    password_data: bytes
    domains: list[bytes]
    notes: bytes
    updated: datetime  # Client's timestamp


class StorageDelete(BaseModel):
    id: str
    updated: datetime  # Client's timestamp for conflict detection


class SyncPushRequest(BaseModel):
    creates: list[StorageCreateUpdate] = []
    updates: list[StorageCreateUpdate] = []
    deletes: list[StorageDelete] = []


class ConflictItem(BaseModel):
    id: str
    client_updated: datetime
    server_updated: datetime
    reason: str


class SyncPushResponse(BaseModel):
    applied: int
    conflicts: list[ConflictItem]


@sync_router.get("/changes", response_model=SyncChangesResponse)
async def get_changes(
    since: datetime | None = None,
    limit: int = 100,
    cursor: str | None = None,
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
            ) from None

    # Order by updated, then id for stable pagination
    query = query.order_by(Storage.updated, Storage.id).limit(limit + 1)  # pyright: ignore[reportArgumentType]

    results = db.exec(query).all()

    has_more = len(results) > limit
    items = results[:limit]

    next_cursor = None
    if has_more and items:
        last_item = items[-1]
        next_cursor = f"{last_item.updated.isoformat()}_{last_item.id}"

    changes: list[StorageChange] = []
    for item in items:
        # Fetch domains for this storage item
        domain_records = db.exec(
            select(Domain).join(StorageDomain).where(StorageDomain.storage_id == item.id)
        ).all()

        domains_list = [d.encrypted_domain for d in domain_records]

        changes.append(
            StorageChange(
                id=item.id,
                username_data=item.username_data,
                password_data=item.password_data,
                domains=domains_list,
                notes=item.notes,
                created_at=item.created_at,
                updated=item.updated,
                deleted_at=item.deleted_at,
            )
        )

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
    conflicts: list[ConflictItem] = []

    # Process creates
    for create_item in payload.creates:
        existing = db.exec(
            select(Storage).where(Storage.id == create_item.id, Storage.user_id == current_user.id)
        ).first()

        if existing and existing.updated > create_item.updated:
            # Item already exists and has newer version - conflict
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
        if existing:
            # Delete existing storage domains
            existing_domains = db.exec(
                select(StorageDomain).where(StorageDomain.storage_id == create_item.id)
            ).all()
            for sd in existing_domains:
                db.delete(sd)
            db.delete(existing)

        new_storage = Storage(
            id=create_item.id,
            user_id=current_user.id,
            username_data=create_item.username_data,
            password_data=create_item.password_data,
            notes=create_item.notes,
            created_at=create_item.updated if not existing else existing.created_at,
            updated=create_item.updated,
            deleted_at=None,
        )
        db.add(new_storage)

        # Create domain records for each domain
        for idx, domain_bytes in enumerate(create_item.domains):
            domain = Domain(
                id=f"{create_item.id}_{idx + 1}",
                encrypted_domain=domain_bytes,
            )
            db.add(domain)

            storage_domain = StorageDomain(
                id=f"sd_{create_item.id}_{domain.id}",
                storage_id=create_item.id,
                domain_id=domain.id,
            )
            db.add(storage_domain)

        applied_count += 1

    # Process updates
    for update_item in payload.updates:
        existing = db.exec(
            select(Storage).where(Storage.id == update_item.id, Storage.user_id == current_user.id)
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

        # Apply update with client timestamp
        existing.username_data = update_item.username_data
        existing.password_data = update_item.password_data
        existing.notes = update_item.notes
        existing.updated = update_item.updated
        existing.deleted_at = None  # Undelete if was deleted

        # Delete existing domain relationships and create new ones
        existing_domains = db.exec(
            select(StorageDomain).where(StorageDomain.storage_id == update_item.id)
        ).all()
        for sd in existing_domains:
            db.delete(sd)

        # Create new domain records
        for idx, domain_bytes in enumerate(update_item.domains):
            domain = Domain(
                id=f"{update_item.id}_{idx}_{update_item.updated.timestamp()}",
                encrypted_domain=domain_bytes,
            )
            db.add(domain)

            storage_domain = StorageDomain(
                id=f"sd_{update_item.id}_{domain.id}",
                storage_id=update_item.id,
                domain_id=domain.id,
            )
            db.add(storage_domain)

        db.add(existing)
        applied_count += 1

    # Process deletes (soft delete)
    for delete_item in payload.deletes:
        existing = db.exec(
            select(Storage).where(Storage.id == delete_item.id, Storage.user_id == current_user.id)
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

        # Apply soft delete with client timestamp
        existing.deleted_at = delete_item.updated
        existing.updated = delete_item.updated

        db.add(existing)
        applied_count += 1

    db.commit()

    return SyncPushResponse(
        applied=applied_count,
        conflicts=conflicts,
    )
