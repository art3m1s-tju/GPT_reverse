"""Unit tests for core proxy logic."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from gpt_proxy.core.proxy import proxy_request, prepare_headers, ProxyResult
from gpt_proxy.core.openai_client import OpenAIClient


class TestPrepareHeaders:
    """Tests for header preparation."""

    def test_strips_hop_by_hop_headers(self):
        headers = {
            "host": "example.com",
            "connection": "keep-alive",
            "content-type": "application/json",
            "authorization": "Bearer test-key",
        }
        result = prepare_headers(headers)
        assert "host" not in result
        assert "connection" not in result
        assert result["content-type"] == "application/json"
        assert result["authorization"] == "Bearer test-key"

    def test_injects_api_key(self):
        headers = {"content-type": "application/json"}
        result = prepare_headers(headers, api_key="sk-test-key")
        # Check case-insensitive match
        assert any(k.lower() == "authorization" and v == "Bearer sk-test-key" for k, v in result.items())

    def test_overrides_authorization(self):
        headers = {"authorization": "Bearer old-key"}
        result = prepare_headers(headers, api_key="sk-new-key")
        # Authorization header should be replaced with new key (using capitalized form)
        assert result["Authorization"] == "Bearer sk-new-key"


class TestProxyRequest:
    """Tests for proxy_request function."""

    @pytest.mark.asyncio
    async def test_non_streaming_request(self):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.content = b'{"test": "response"}'

        with patch.object(OpenAIClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await proxy_request(
                method="POST",
                path="/v1/chat/completions",
                headers={"content-type": "application/json"},
                body=b'{"test": "request"}',
                stream=False,
            )

            assert isinstance(result, ProxyResult)
            assert result.status_code == 200
            assert result.body == b'{"test": "response"}'
            assert result.stream is None

    @pytest.mark.asyncio
    async def test_streaming_request(self):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({"content-type": "text/event-stream"})

        async def mock_aiter_lines():
            yield 'data: {"test": "chunk1"}'
            yield ""
            yield 'data: [DONE]'
            yield ""

        mock_response.aiter_lines = mock_aiter_lines

        with patch.object(OpenAIClient, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            result = await proxy_request(
                method="POST",
                path="/v1/chat/completions",
                headers={"content-type": "application/json"},
                body=b'{"stream": true}',
                stream=True,
            )

            assert isinstance(result, ProxyResult)
            assert result.status_code == 200
            assert result.stream is not None
            assert result.body is None
