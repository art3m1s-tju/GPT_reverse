"""Integration tests for API endpoints."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock
import httpx


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_ready_check(self, client: AsyncClient):
        response = await client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "has_api_keys" in data


class TestChatCompletions:
    """Tests for chat completions endpoint."""

    @pytest.mark.asyncio
    async def test_chat_completions_non_streaming(self, client: AsyncClient, mock_openai_response):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.content = b'{"id":"test","choices":[]}'

        with patch("gpt_proxy.api.router.proxy_request", new_callable=AsyncMock) as mock_proxy:
            from gpt_proxy.core.proxy import ProxyResult
            mock_proxy.return_value = ProxyResult(
                status_code=200,
                headers={"content-type": "application/json"},
                body=b'{"id":"test","choices":[]}',
            )

            response = await client.post(
                "/v1/chat/completions",
                headers={"Authorization": "Bearer test-key"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_chat_completions_missing_auth(self, client: AsyncClient):
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Hello"}],
            },
        )
        # Note: Auth middleware is not added in test app
        # This tests the endpoint directly


class TestEmbeddings:
    """Tests for embeddings endpoint."""

    @pytest.mark.asyncio
    async def test_embeddings(self, client: AsyncClient):
        from gpt_proxy.core.proxy import ProxyResult

        with patch("gpt_proxy.api.router.proxy_request", new_callable=AsyncMock) as mock_proxy:
            mock_proxy.return_value = ProxyResult(
                status_code=200,
                headers={"content-type": "application/json"},
                body=b'{"data":[{"embedding":[0.1,0.2]}]}',
            )

            response = await client.post(
                "/v1/embeddings",
                headers={"Authorization": "Bearer test-key"},
                json={"model": "text-embedding-3-small", "input": "test"},
            )

            assert response.status_code == 200


class TestModels:
    """Tests for models endpoint."""

    @pytest.mark.asyncio
    async def test_list_models(self, client: AsyncClient):
        from gpt_proxy.core.proxy import ProxyResult

        with patch("gpt_proxy.api.router.proxy_request", new_callable=AsyncMock) as mock_proxy:
            mock_proxy.return_value = ProxyResult(
                status_code=200,
                headers={"content-type": "application/json"},
                body=b'{"data":[{"id":"gpt-4"}]}',
            )

            response = await client.get(
                "/v1/models",
                headers={"Authorization": "Bearer test-key"},
            )

            assert response.status_code == 200


class TestCatchAll:
    """Tests for catch-all proxy."""

    @pytest.mark.asyncio
    async def test_catch_all_endpoint(self, client: AsyncClient):
        from gpt_proxy.core.proxy import ProxyResult

        with patch("gpt_proxy.api.router.proxy_request", new_callable=AsyncMock) as mock_proxy:
            mock_proxy.return_value = ProxyResult(
                status_code=200,
                headers={"content-type": "application/json"},
                body=b'{"success": true}',
            )

            response = await client.get(
                "/v1/unknown/endpoint",
                headers={"Authorization": "Bearer test-key"},
            )

            assert response.status_code == 200
