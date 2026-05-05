"""Async httpx client configured for OpenAI API."""

import httpx
from contextlib import asynccontextmanager
from typing import AsyncIterator

from gpt_proxy.config import settings


class OpenAIClient:
    """Async HTTP client for OpenAI API with connection pooling."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.openai_api_base_url).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(
                    connect=5.0,
                    read=30.0,
                    write=30.0,
                    pool=5.0,
                ),
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                    keepalive_expiry=30.0,
                ),
                http2=True,
            )
        return self._client

    async def request(
        self,
        method: str,
        path: str,
        headers: dict | None = None,
        content: bytes | None = None,
        stream: bool = False,
    ) -> httpx.Response:
        """Make a request to OpenAI API.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., /v1/chat/completions)
            headers: Request headers
            content: Request body as bytes
            stream: Whether to stream the response

        Returns:
            httpx Response object
        """
        client = await self._get_client()

        # Ensure path starts with /
        if not path.startswith("/"):
            path = "/" + path

        if stream:
            return await client.stream(
                method,
                path,
                headers=headers,
                content=content,
            ).__aenter__()
        else:
            return await client.request(
                method,
                path,
                headers=headers,
                content=content,
            )

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        path: str,
        headers: dict | None = None,
        content: bytes | None = None,
    ) -> AsyncIterator[httpx.Response]:
        """Context manager for streaming requests."""
        client = await self._get_client()

        if not path.startswith("/"):
            path = "/" + path

        async with client.stream(
            method,
            path,
            headers=headers,
            content=content,
        ) as response:
            yield response


# Global client instance
_client: OpenAIClient | None = None


def get_openai_client() -> OpenAIClient:
    """Get the global OpenAI client instance."""
    global _client
    if _client is None:
        _client = OpenAIClient()
    return _client


async def close_openai_client():
    """Close the global OpenAI client."""
    global _client
    if _client:
        await _client.close()
        _client = None
