"""Core proxy logic for forwarding requests to OpenAI."""

from dataclasses import dataclass
from typing import AsyncIterator, Any
import httpx

from gpt_proxy.core.openai_client import get_openai_client
from gpt_proxy.core.streaming import stream_sse_response


# Headers that should not be forwarded (hop-by-hop headers)
HEADERS_TO_STRIP = {
    "host",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "te",
    "trailer",
    "upgrade",
    "proxy-authorization",
    "proxy-authenticate",
    "content-length",  # Will be recalculated
}


@dataclass
class ProxyResult:
    """Result of a proxy request."""

    status_code: int
    headers: dict[str, str]
    body: bytes | None = None
    stream: AsyncIterator[bytes] | None = None


def prepare_headers(headers: dict[str, Any], api_key: str | None = None) -> dict[str, str]:
    """Prepare headers for forwarding to OpenAI.

    Args:
        headers: Original request headers
        api_key: Optional API key to inject

    Returns:
        Cleaned headers ready for forwarding
    """
    result = {}

    for key, value in headers.items():
        # Skip hop-by-hop headers
        if key.lower() in HEADERS_TO_STRIP:
            continue

        # Skip Authorization if we're injecting a new key
        if api_key and key.lower() == "authorization":
            continue

        # Convert to string
        result[key] = str(value)

    # Inject or override Authorization if API key provided
    if api_key:
        result["Authorization"] = f"Bearer {api_key}"

    return result


async def proxy_request(
    method: str,
    path: str,
    headers: dict[str, Any],
    body: bytes | None = None,
    stream: bool = False,
    api_key: str | None = None,
) -> ProxyResult:
    """Core proxy function to forward requests to OpenAI.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g., /v1/chat/completions)
        headers: Request headers
        body: Request body as bytes
        stream: Whether to stream the response
        api_key: Optional API key to use (overrides Authorization header)

    Returns:
        ProxyResult with either body or stream
    """
    client = get_openai_client()

    # Prepare headers
    forward_headers = prepare_headers(headers, api_key)

    if stream:
        # Streaming request
        response = await client.request(
            method=method,
            path=path,
            headers=forward_headers,
            content=body,
            stream=True,
        )

        # Prepare response headers
        response_headers = dict(response.headers)
        for key in HEADERS_TO_STRIP:
            response_headers.pop(key, None)
            response_headers.pop(key.lower(), None)

        # Create streaming iterator
        async def stream_iterator() -> AsyncIterator[bytes]:
            try:
                async for chunk in stream_sse_response(response):
                    yield chunk
            finally:
                await response.aclose()

        return ProxyResult(
            status_code=response.status_code,
            headers=response_headers,
            stream=stream_iterator(),
        )
    else:
        # Non-streaming request
        response = await client.request(
            method=method,
            path=path,
            headers=forward_headers,
            content=body,
            stream=False,
        )

        # Prepare response headers
        response_headers = dict(response.headers)
        for key in HEADERS_TO_STRIP:
            response_headers.pop(key, None)
            response_headers.pop(key.lower(), None)

        return ProxyResult(
            status_code=response.status_code,
            headers=response_headers,
            body=response.content,
        )
