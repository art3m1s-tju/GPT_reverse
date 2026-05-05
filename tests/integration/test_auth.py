"""Integration tests for auth endpoints."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


class TestAuthEndpoints:
    """Tests for authentication endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_auth_help(self, client: AsyncClient):
        response = await client.get("/auth/help")
        assert response.status_code == 200
        data = response.json()
        assert "steps" in data

    @pytest.mark.asyncio
    async def test_login_invalid_token(self, client: AsyncClient):
        response = await client.post(
            "/auth/login",
            json={"session_token": "invalid-token"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, mock_auth_response):
        with patch(
            "gpt_proxy.services.auth_manager.AuthManager.exchange_session_token",
            new_callable=AsyncMock,
        ) as mock_exchange:
            from gpt_proxy.services.auth_manager import UserSession
            from datetime import datetime, timedelta

            mock_exchange.return_value = UserSession(
                session_id="test-session-id",
                user_id="user-123",
                email="test@example.com",
                access_token="access-token-123",
                session_token="session-token",
                expires_at=datetime.now() + timedelta(hours=1),
            )

            response = await client.post(
                "/auth/login",
                json={"session_token": "valid-token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["session_id"] == "test-session-id"
            assert data["user_email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_chat_without_auth(self, client: AsyncClient):
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_chat_with_invalid_session(self, client: AsyncClient):
        response = await client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer invalid-session-id"},
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 401
