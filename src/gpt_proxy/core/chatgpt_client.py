"""ChatGPT backend API client."""

import httpx
from typing import AsyncIterator
from logging import getLogger

logger = getLogger(__name__)


class ChatGPTClient:
    """ChatGPT backend API client using access token."""

    BACKEND_API = "https://chat.openai.com/backend-api"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BACKEND_API,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(120.0, connect=30.0),
            )
        return self._client

    async def chat_completions(
        self,
        model: str,
        messages: list[dict],
        stream: bool = False,
        **kwargs,
    ) -> httpx.Response | AsyncIterator[bytes]:
        """Send chat completion request."""
        client = await self._get_client()

        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs,
        }

        if stream:
            return await self._stream_chat(client, payload)
        else:
            return await client.post("/chat/completions", json=payload)

    async def _stream_chat(
        self,
        client: httpx.AsyncClient,
        payload: dict,
    ) -> AsyncIterator[bytes]:
        """Stream chat completion response."""
        async with client.stream("POST", "/chat/completions", json=payload) as response:
            async for chunk in response.aiter_bytes():
                yield chunk

    async def models(self) -> httpx.Response:
        """Get available models."""
        client = await self._get_client()
        return await client.get("/models")

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


async def chatgpt_request(
    access_token: str,
    method: str,
    path: str,
    body: bytes | None = None,
) -> httpx.Response:
    """Make non-streaming request to ChatGPT backend API."""
    client = httpx.AsyncClient(
        base_url=ChatGPTClient.BACKEND_API,
        headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        },
        timeout=httpx.Timeout(120.0, connect=30.0),
    )

    try:
        response = await client.request(method, path, content=body)
        return response
    finally:
        await client.aclose()


async def chatgpt_stream(
    access_token: str,
    method: str,
    path: str,
    body: bytes | None = None,
) -> AsyncIterator[bytes]:
    """Make streaming request to ChatGPT backend API."""
    client = httpx.AsyncClient(
        base_url=ChatGPTClient.BACKEND_API,
        headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/event-stream",
        },
        timeout=httpx.Timeout(120.0, connect=30.0),
    )

    try:
        async with client.stream(method, path, content=body) as response:
            async for chunk in response.aiter_bytes():
                yield chunk
    finally:
        await client.aclose()