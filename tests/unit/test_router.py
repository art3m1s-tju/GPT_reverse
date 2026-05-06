"""Unit tests for API router."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from gpt_proxy.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


class TestAuthRequired:
    """Tests that protected endpoints require authentication."""

    @pytest.mark.asyncio
    async def test_models_requires_auth(self, client):
        response = await client.get("/v1/models")
        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"]["code"] == "missing_auth"

    @pytest.mark.asyncio
    async def test_chat_completions_requires_auth(self, client):
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"]["code"] == "missing_auth"

    @pytest.mark.asyncio
    async def test_invalid_session_returns_401(self, client):
        response = await client.get(
            "/v1/models",
            headers={"Authorization": "Bearer invalid-session-id"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"]["code"] == "session_expired"

    @pytest.mark.asyncio
    async def test_malformed_auth_header_returns_401(self, client):
        response = await client.get(
            "/v1/models",
            headers={"Authorization": "Token abc123"},
        )
        assert response.status_code == 401


class TestHealthEndpoints:
    """Tests for health check endpoints (no auth required)."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_ready_endpoint(self, client):
        response = await client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


class TestModelsEndpoint:
    """Tests for /v1/models endpoint."""

    @pytest.mark.asyncio
    async def test_models_with_valid_session(self, client):
        mock_response = MagicMock()
        mock_response.content = b'{"data": [{"id": "gpt-4"}]}'
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}

        with patch("gpt_proxy.api.router.get_auth_manager") as mock_get_auth, \
             patch("gpt_proxy.api.router.chatgpt_request", new_callable=AsyncMock, return_value=mock_response):
            mock_auth = MagicMock()
            mock_auth.get_valid_token = AsyncMock(return_value="valid-access-token")
            mock_get_auth.return_value = mock_auth

            response = await client.get(
                "/v1/models",
                headers={"Authorization": "Bearer valid-session-id"},
            )
            assert response.status_code == 200


class TestChatCompletionsEndpoint:
    """Tests for /v1/chat/completions endpoint."""

    @pytest.mark.asyncio
    async def test_non_streaming_completions(self, client):
        mock_response = MagicMock()
        mock_response.content = b'{"choices": [{"message": {"content": "Hello!"}}]}'
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}

        with patch("gpt_proxy.api.router.get_auth_manager") as mock_get_auth, \
             patch("gpt_proxy.api.router.chatgpt_request", new_callable=AsyncMock, return_value=mock_response):
            mock_auth = MagicMock()
            mock_auth.get_valid_token = AsyncMock(return_value="valid-access-token")
            mock_get_auth.return_value = mock_auth

            response = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer valid-session-id"},
                json={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hello!"}],
                },
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_streaming_completions(self, client):
        async def mock_stream(**kwargs):
            yield b'data: {"choices": [{"delta": {"content": "Hi"}}]}\n\n'
            yield b'data: [DONE]\n\n'

        with patch("gpt_proxy.api.router.get_auth_manager") as mock_get_auth, \
             patch("gpt_proxy.api.router.chatgpt_stream", side_effect=lambda **kwargs: mock_stream()):
            mock_auth = MagicMock()
            mock_auth.get_valid_token = AsyncMock(return_value="valid-access-token")
            mock_get_auth.return_value = mock_auth

            response = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer valid-session-id"},
                json={
                    "model": "gpt-4",
                    "messages": [{"role": "user", "content": "Hello!"}],
                    "stream": True,
                },
            )
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
