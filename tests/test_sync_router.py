"""Unit tests for sync endpoints."""

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from core.models import Domain, Storage, StorageDomain, User


class TestSyncChangesEndpoint:
    """Tests for GET /sync/changes endpoint."""

    def test_get_changes_requires_authentication(self, client: TestClient) -> None:
        """Test that endpoint requires authentication."""
        response = client.get("/sync/changes")
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]

    def test_get_all_changes_initial_sync(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        auth_headers: dict[str, str],
        test_storage_items: list[Storage],
    ) -> None:
        """Test fetching all changes (initial sync without since parameter)."""
        response = client.get("/sync/changes", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert len(data["changes"]) == 5
        assert data["has_more"] is False
        assert data["next_cursor"] is None

        # Verify changes are ordered by updated timestamp
        changes = data["changes"]
        for i in range(len(changes) - 1):
            assert changes[i]["updated"] <= changes[i + 1]["updated"]

    def test_get_changes_since_timestamp(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        auth_headers: dict[str, str],
        test_storage_items: list[Storage],
    ) -> None:
        """Test fetching changes since a specific timestamp."""
        since = datetime(2026, 1, 13, 10, 2, 0).isoformat()
        response = client.get(f"/sync/changes?since={since}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should only get items with index 3 and 4 (updated at 10:03 and 10:04)
        assert len(data["changes"]) == 2
        assert data["has_more"] is False

    def test_get_changes_with_pagination(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        auth_headers: dict[str, str],
        test_storage_items: list[Storage],
    ) -> None:
        """Test pagination with limit parameter."""
        response = client.get("/sync/changes?limit=2", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert len(data["changes"]) == 2
        assert data["has_more"] is True
        assert data["next_cursor"] is not None

        # Fetch next page using cursor
        cursor = data["next_cursor"]
        response2 = client.get(f"/sync/changes?limit=2&cursor={cursor}", headers=auth_headers)

        assert response2.status_code == 200
        data2 = response2.json()

        assert len(data2["changes"]) == 2
        assert data2["has_more"] is True

        # Verify no overlap between pages
        first_ids = {change["id"] for change in data["changes"]}
        second_ids = {change["id"] for change in data2["changes"]}
        assert len(first_ids.intersection(second_ids)) == 0

    def test_get_changes_max_limit(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test that limit is capped at 1000."""
        response = client.get("/sync/changes?limit=5000", headers=auth_headers)

        assert response.status_code == 200
        # Should succeed (limit is capped internally, not return error)

    def test_get_changes_invalid_cursor(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test handling of invalid cursor format."""
        response = client.get("/sync/changes?cursor=invalid_cursor", headers=auth_headers)

        assert response.status_code == 400
        assert "Invalid cursor format" in response.json()["detail"]

    def test_get_changes_includes_deleted_items(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        auth_headers: dict[str, str],
        test_storage_items: list[Storage],
    ) -> None:
        """Test that soft-deleted items are included in sync."""
        # Soft delete one item
        item = test_storage_items[0]
        item.deleted_at = datetime.now()
        item.updated = datetime.now()
        session.add(item)
        session.commit()

        response = client.get("/sync/changes", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should still get 5 items, including the deleted one
        assert len(data["changes"]) == 5

        # Find the deleted item
        deleted_change = next(c for c in data["changes"] if c["id"] == item.id)
        assert deleted_change["deleted_at"] is not None

    def test_get_changes_user_isolation(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        auth_headers: dict[str, str],
        test_storage_items: list[Storage],
    ) -> None:
        """Test that users only see their own changes."""
        # Create another user with storage items
        other_user = User(
            id=str(uuid4()),
            auth_id=str(uuid4()),
            encryption_key=b"other_key",
        )
        session.add(other_user)

        other_storage_id = str(uuid4())
        other_storage = Storage(
            id=other_storage_id,
            user_id=other_user.id,
            username_data=b"other_username",
            password_data=b"other_password",
            notes=b"other_notes",
            created_at=datetime.now(),
            updated=datetime.now(),
            deleted_at=None,
        )
        session.add(other_storage)

        # Create domain for other user's storage
        domain = Domain(
            id=str(uuid4()),
            encrypted_domain=b"other_domain",
        )
        session.add(domain)
        storage_domain = StorageDomain(
            id=str(uuid4()),
            storage_id=other_storage_id,
            domain_id=domain.id,
        )
        session.add(storage_domain)

        session.commit()

        response = client.get("/sync/changes", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should only get test_user's 5 items, not other_user's item
        assert len(data["changes"]) == 5
        all_ids = {change["id"] for change in data["changes"]}
        assert other_storage.id not in all_ids

    def test_get_changes_response_structure(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        test_storage_items: list[Storage],
    ) -> None:
        """Test that response includes all required fields."""
        response = client.get("/sync/changes?limit=1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "changes" in data
        assert "next_cursor" in data
        assert "has_more" in data

        # Check change structure
        change = data["changes"][0]
        required_fields = [
            "id",
            "username_data",
            "password_data",
            "domains",
            "notes",
            "created_at",
            "updated",
            "deleted_at",
        ]
        for field in required_fields:
            assert field in change


class TestSyncPushEndpoint:
    """Tests for POST /sync/push endpoint."""

    def test_push_requires_authentication(self, client: TestClient) -> None:
        """Test that endpoint requires authentication."""
        response = client.post(
            "/sync/push",
            json={
                "creates": [],
                "updates": [],
                "deletes": [],
            },
        )
        assert response.status_code == 401

    def test_push_create_new_items(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """Test creating new storage items."""
        new_id = str(uuid4())
        client_time = datetime(2026, 1, 13, 12, 0, 0)

        payload = {
            "creates": [
                {
                    "id": new_id,
                    "username_data": "bmV3X3VzZXJuYW1l",  # base64-like for testing
                    "password_data": "bmV3X3Bhc3N3b3Jk",
                    "domains": ["bmV3X2RvbWFpbnM=", "Ym13X2RvbWFpbjI="],
                    "notes": "bmV3X25vdGVz",
                    "updated": client_time.isoformat(),
                }
            ],
            "updates": [],
            "deletes": [],
        }

        response = client.post("/sync/push", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["applied"] == 1
        assert len(data["conflicts"]) == 0

        # Verify item was created in database
        created_item = session.get(Storage, new_id)
        assert created_item is not None
        assert created_item.user_id == test_user.id
        assert created_item.deleted_at is None
        # Client timestamp should be preserved
        assert created_item.updated == client_time

    def test_push_update_existing_items(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        auth_headers: dict[str, str],
        test_storage_items: list[Storage],
    ) -> None:
        """Test updating existing storage items."""
        item = test_storage_items[0]
        client_time = datetime.now()

        payload = {
            "creates": [],
            "updates": [
                {
                    "id": item.id,
                    "username_data": "dXBkYXRlZF91c2VybmFtZQ==",
                    "password_data": "dXBkYXRlZF9wYXNzd29yZA==",
                    "domains": ["dXBkYXRlZF9kb21haW5z"],
                    "notes": "dXBkYXRlZF9ub3Rlcw==",
                    "updated": client_time.isoformat(),
                }
            ],
            "deletes": [],
        }

        response = client.post("/sync/push", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["applied"] == 1
        assert len(data["conflicts"]) == 0

        # Verify item was updated
        session.refresh(item)
        assert item.username_data.decode() == "dXBkYXRlZF91c2VybmFtZQ=="
        assert item.updated >= client_time

    def test_push_delete_items(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        auth_headers: dict[str, str],
        test_storage_items: list[Storage],
    ) -> None:
        """Test soft-deleting storage items."""
        item = test_storage_items[0]
        client_time = datetime.now()

        payload = {
            "creates": [],
            "updates": [],
            "deletes": [
                {
                    "id": item.id,
                    "updated": client_time.isoformat(),
                }
            ],
        }

        response = client.post("/sync/push", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["applied"] == 1
        assert len(data["conflicts"]) == 0

        # Verify item was soft-deleted
        session.refresh(item)
        assert item.deleted_at is not None
        assert item.updated >= client_time

    def test_push_conflict_server_newer(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        auth_headers: dict[str, str],
        test_storage_items: list[Storage],
    ) -> None:
        """Test conflict when server has newer timestamp (last-write-wins)."""
        item = test_storage_items[0]

        # Update item on server with recent timestamp
        server_time = datetime.now()
        item.updated = server_time
        session.add(item)
        session.commit()

        # Try to update with older client timestamp
        client_time = server_time - timedelta(minutes=5)

        payload = {
            "creates": [],
            "updates": [
                {
                    "id": item.id,
                    "username_data": "b2xkX2RhdGE=",
                    "password_data": "b2xkX2RhdGE=",
                    "domains": ["b2xkX2RhdGE="],
                    "notes": "b2xkX2RhdGE=",
                    "updated": client_time.isoformat(),
                }
            ],
            "deletes": [],
        }

        response = client.post("/sync/push", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["applied"] == 0
        assert len(data["conflicts"]) == 1

        conflict = data["conflicts"][0]
        assert conflict["id"] == item.id
        assert "Server has newer version" in conflict["reason"]
        assert conflict["client_updated"] == client_time.isoformat()

    def test_push_conflict_update_nonexistent(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test conflict when trying to update non-existent item."""
        nonexistent_id = str(uuid4())

        payload = {
            "creates": [],
            "updates": [
                {
                    "id": nonexistent_id,
                    "username_data": "ZGF0YQ==",
                    "password_data": "ZGF0YQ==",
                    "domains": ["ZGF0YQ=="],
                    "notes": "ZGF0YQ==",
                    "updated": datetime.now().isoformat(),
                }
            ],
            "deletes": [],
        }

        response = client.post("/sync/push", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["applied"] == 0
        assert len(data["conflicts"]) == 1
        assert "Item not found on server" in data["conflicts"][0]["reason"]

    def test_push_delete_already_deleted(
        self,
        client: TestClient,
        session: Session,
        auth_headers: dict[str, str],
    ) -> None:
        """Test deleting an item that doesn't exist (idempotent)."""
        nonexistent_id = str(uuid4())

        payload = {
            "creates": [],
            "updates": [],
            "deletes": [
                {
                    "id": nonexistent_id,
                    "updated": datetime.now().isoformat(),
                }
            ],
        }

        response = client.post("/sync/push", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should not count as applied or conflict (idempotent)
        assert data["applied"] == 0
        assert len(data["conflicts"]) == 0

    def test_push_mixed_operations(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        auth_headers: dict[str, str],
        test_storage_items: list[Storage],
    ) -> None:
        """Test pushing creates, updates, and deletes in one request."""
        new_id = str(uuid4())
        update_item = test_storage_items[0]
        delete_item = test_storage_items[1]
        client_time = datetime.now()

        payload = {
            "creates": [
                {
                    "id": new_id,
                    "username_data": "bmV3",
                    "password_data": "bmV3",
                    "domains": ["bmV3"],
                    "notes": "bmV3",
                    "updated": client_time.isoformat(),
                }
            ],
            "updates": [
                {
                    "id": update_item.id,
                    "username_data": "dXBkYXRlZA==",
                    "password_data": "dXBkYXRlZA==",
                    "domains": ["dXBkYXRlZA=="],
                    "notes": "dXBkYXRlZA==",
                    "updated": client_time.isoformat(),
                }
            ],
            "deletes": [
                {
                    "id": delete_item.id,
                    "updated": client_time.isoformat(),
                }
            ],
        }

        response = client.post("/sync/push", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["applied"] == 3
        assert len(data["conflicts"]) == 0

        # Verify all operations
        created = session.get(Storage, new_id)
        assert created is not None

        session.refresh(update_item)
        assert update_item.username_data.decode() == "dXBkYXRlZA=="

        session.refresh(delete_item)
        assert delete_item.deleted_at is not None

    def test_push_update_undeletes_item(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        auth_headers: dict[str, str],
        test_storage_items: list[Storage],
    ) -> None:
        """Test that updating a soft-deleted item undeletes it."""
        item = test_storage_items[0]

        # Soft delete the item first
        item.deleted_at = datetime.now()
        session.add(item)
        session.commit()

        # Now update it
        client_time = datetime.now()
        payload = {
            "creates": [],
            "updates": [
                {
                    "id": item.id,
                    "username_data": "cmVzdG9yZWQ=",
                    "password_data": "cmVzdG9yZWQ=",
                    "domains": ["cmVzdG9yZWQ="],
                    "notes": "cmVzdG9yZWQ=",
                    "updated": client_time.isoformat(),
                }
            ],
            "deletes": [],
        }

        response = client.post("/sync/push", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["applied"] == 1

        # Verify item is no longer deleted
        session.refresh(item)
        assert item.deleted_at is None
        assert item.username_data.decode() == "cmVzdG9yZWQ="

    def test_push_user_isolation(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """Test that users cannot modify other users' items."""
        # Create another user and their storage
        other_user = User(
            id=str(uuid4()),
            auth_id=str(uuid4()),
            encryption_key=b"other_key",
        )
        session.add(other_user)

        other_storage_id = str(uuid4())
        other_storage = Storage(
            id=other_storage_id,
            user_id=other_user.id,
            username_data=b"other_data",
            password_data=b"other_data",
            notes=b"other_data",
            created_at=datetime.now(),
            updated=datetime.now(),
            deleted_at=None,
        )
        session.add(other_storage)

        # Create domain for other user's storage
        domain = Domain(
            id=str(uuid4()),
            encrypted_domain=b"other_domain",
        )
        session.add(domain)
        storage_domain = StorageDomain(
            id=str(uuid4()),
            storage_id=other_storage_id,
            domain_id=domain.id,
        )
        session.add(storage_domain)

        session.commit()

        # Try to update other user's item
        payload = {
            "creates": [],
            "updates": [
                {
                    "id": other_storage.id,
                    "username_data": "aGFja2Vk",
                    "password_data": "aGFja2Vk",
                    "domains": ["aGFja2Vk"],
                    "notes": "aGFja2Vk",
                    "updated": datetime.now().isoformat(),
                }
            ],
            "deletes": [],
        }

        response = client.post("/sync/push", json=payload, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should be treated as "not found" conflict
        assert data["applied"] == 0
        assert len(data["conflicts"]) == 1
        assert "Item not found on server" in data["conflicts"][0]["reason"]

        # Verify other user's item was not modified
        session.refresh(other_storage)
        assert other_storage.username_data == b"other_data"
