"""Unit tests for auth manager."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import httpx
import json

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
        with patch.object(AuthManager, '_load_sessions'), \
             patch.object(AuthManager, '_save_sessions'):
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


class TestAuthManagerErrorHandling:
    """Tests for error handling in auth manager."""

    @pytest.mark.asyncio
    async def test_exchange_token_empty_response(self):
        """Test handling of empty response body."""
        manager = AuthManager()

        with patch.object(manager, '_get_client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.text = ""
            mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http_client

            result = await manager.exchange_session_token("test-token")
            assert result is None

    @pytest.mark.asyncio
    async def test_exchange_token_html_response(self):
        """Test handling of HTML response (Cloudflare challenge)."""
        manager = AuthManager()

        with patch.object(manager, '_get_client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.headers = {"content-type": "text/html"}
            mock_response.text = "<html><body>Cloudflare challenge</body></html>"

            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http_client

            result = await manager.exchange_session_token("test-token")
            assert result is None

    @pytest.mark.asyncio
    async def test_cloudflare_detection(self):
        """Test Cloudflare challenge detection."""
        manager = AuthManager()

        # Test 403 with Cloudflare
        response = MagicMock()
        response.status_code = 403
        response.text = "<html>Just a moment... Checking your browser</html>"
        assert manager._is_cloudflare_challenge(response) is True

        # Test normal 403
        response.text = "<html>Access Denied</html>"
        assert manager._is_cloudflare_challenge(response) is False

        # Test 503 with Cloudflare
        response.status_code = 503
        response.text = "<html>cloudflare challenge-platform</html>"
        assert manager._is_cloudflare_challenge(response) is True

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test handling of timeout errors."""
        manager = AuthManager()

        with patch.object(manager, '_get_client') as mock_client:
            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.return_value = mock_http_client

            result = await manager.exchange_session_token("test-token")
            assert result is None


class TestTokenValidation:
    """Tests for token validation."""

    @pytest.mark.asyncio
    async def test_validate_valid_token(self):
        """Test validation of valid token."""
        manager = AuthManager()

        with patch.object(manager, '_get_client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json.return_value = {
                "user": {"email": "test@example.com"},
                "accessToken": "test-access-token"
            }

            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http_client

            result = await manager.validate_session_token("valid-token")
            assert result["valid"] is True
            assert result["user_email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_validate_invalid_token(self):
        """Test validation of invalid token."""
        manager = AuthManager()

        with patch.object(manager, '_get_client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401

            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http_client

            result = await manager.validate_session_token("invalid-token")
            assert result["valid"] is False
            assert result["error"] == "invalid_token"

    @pytest.mark.asyncio
    async def test_validate_cloudflare_challenge(self):
        """Test validation when Cloudflare challenge is present."""
        manager = AuthManager()

        with patch.object(manager, '_get_client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.text = "<html>Just a moment... Cloudflare</html>"

            mock_http_client = AsyncMock()
            mock_http_client.get = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_http_client

            result = await manager.validate_session_token("test-token")
            assert result["valid"] is False
            assert result["error"] == "cloudflare_challenge"
