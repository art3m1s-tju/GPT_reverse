"""Unit tests for auth manager."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from gpt_proxy.services.auth_manager import AuthManager, UserSession


class TestAuthManager:
    """Tests for authentication manager."""

    def test_create_session(self):
        manager = AuthManager()
        session = UserSession(
            session_id="test-id",
            user_id="user-123",
            email="test@example.com",
            access_token="token-123",
            session_token="session-123",
            expires_at=datetime.now() + timedelta(hours=1),
        )

        manager.create_session(session)
        assert "test-id" in manager.sessions

    def test_get_session(self):
        manager = AuthManager()
        session = UserSession(
            session_id="test-id",
            user_id="user-123",
            email="test@example.com",
            access_token="token-123",
            session_token="session-123",
            expires_at=datetime.now() + timedelta(hours=1),
        )
        manager.create_session(session)

        result = manager.get_session("test-id")
        assert result == session

    def test_invalidate_session(self):
        manager = AuthManager()
        session = UserSession(
            session_id="test-id",
            user_id="user-123",
            email="test@example.com",
            access_token="token-123",
            session_token="session-123",
            expires_at=datetime.now() + timedelta(hours=1),
        )
        manager.create_session(session)

        result = manager.invalidate_session("test-id")
        assert result is True
        assert manager.sessions["test-id"].is_active is False

    def test_list_sessions(self):
        manager = AuthManager()
        session = UserSession(
            session_id="test-id",
            user_id="user-123",
            email="test@example.com",
            access_token="token-123",
            session_token="session-123",
            expires_at=datetime.now() + timedelta(hours=1),
        )
        manager.create_session(session)

        sessions = manager.list_sessions()
        assert len(sessions) == 1
        assert sessions[0]["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_valid_token(self):
        manager = AuthManager()
        session = UserSession(
            session_id="test-id",
            user_id="user-123",
            email="test@example.com",
            access_token="token-123",
            session_token="session-123",
            expires_at=datetime.now() + timedelta(hours=1),
        )
        manager.create_session(session)

        token = await manager.get_valid_token("test-id")
        assert token == "token-123"

    @pytest.mark.asyncio
    async def test_get_valid_token_expired(self):
        manager = AuthManager()
        session = UserSession(
            session_id="test-id",
            user_id="user-123",
            email="test@example.com",
            access_token="old-token",
            session_token="session-123",
            expires_at=datetime.now() - timedelta(hours=1),  # Expired
        )
        manager.create_session(session)

        # Should try to refresh and fail (no mock)
        token = await manager.get_valid_token("test-id")
        assert token is None
