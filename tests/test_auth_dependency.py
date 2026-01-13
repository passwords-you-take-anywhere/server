"""Unit tests for authentication dependency."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from core.models import Session as UserSession
from core.models import User


class TestAuthenticationDependency:
    """Tests for authentication dependency."""

    def test_missing_session_cookie_and_header(
        self,
        client: TestClient,
    ) -> None:
        """Test that missing authentication returns 401."""
        response = client.get("/sync/changes")
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]

    def test_invalid_session_id(
        self,
        client: TestClient,
    ) -> None:
        """Test that invalid session ID returns 401."""
        invalid_session_id = str(uuid4())
        headers = {"X-Session-Id": invalid_session_id}

        response = client.get("/sync/changes", headers=headers)
        assert response.status_code == 401
        assert "Invalid or expired session" in response.json()["detail"]

    def test_valid_session_header(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        """Test that valid session in header authenticates successfully."""
        response = client.get("/sync/changes", headers=auth_headers)
        assert response.status_code == 200

    def test_valid_session_cookie(
        self,
        client: TestClient,
        test_session: UserSession,
    ) -> None:
        """Test that valid session cookie authenticates successfully."""
        client.cookies.set("session_id", test_session.id)
        response = client.get("/sync/changes")
        assert response.status_code == 200

    def test_header_takes_precedence_over_cookie(
        self,
        client: TestClient,
        session: Session,
        test_user: User,
        test_session: UserSession,
    ) -> None:
        """Test that X-Session-Id header takes precedence over cookie."""
        # Create another valid session
        another_session = UserSession(
            id=str(uuid4()),
            user_id=test_user.id,
        )
        session.add(another_session)
        session.commit()

        # Set cookie to one session
        client.cookies.set("session_id", test_session.id)

        # Set header to another session
        headers = {"X-Session-Id": another_session.id}

        # Both are valid, so should succeed (header used)
        response = client.get("/sync/changes", headers=headers)
        assert response.status_code == 200
