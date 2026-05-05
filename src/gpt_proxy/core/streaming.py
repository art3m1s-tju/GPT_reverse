"""SSE (Server-Sent Events) streaming handler."""

from typing import AsyncIterator, Callable
import httpx


async def stream_sse_response(
    response: httpx.Response,
    on_chunk: Callable[[bytes], None] | None = None,
) -> AsyncIterator[bytes]:
    """Stream SSE response from OpenAI.

    Handles the SSE format where each event is prefixed with "data: "
    and the stream terminates with "data: [DONE]".

    Args:
        response: httpx streaming response
        on_chunk: Optional callback for each chunk

    Yields:
        Raw bytes from the SSE stream
    """
    async for line in response.aiter_lines():
        if not line:
            continue

        # SSE format: each line is "data: <json>"
        chunk = f"{line}\n\n".encode()

        if on_chunk:
            on_chunk(chunk)

        yield chunk


async def parse_sse_stream(
    response: httpx.Response,
) -> AsyncIterator[dict]:
    """Parse SSE stream into JSON objects.

    Args:
        response: httpx streaming response

    Yields:
        Parsed JSON objects from SSE events
    """
    import json

    async for line in response.aiter_lines():
        if not line:
            continue

        # Skip non-data lines
        if not line.startswith("data: "):
            continue

        # Extract data
        data = line[6:]  # Remove "data: " prefix

        # Check for stream end
        if data == "[DONE]":
            break

        try:
            yield json.loads(data)
        except json.JSONDecodeError:
            continue
