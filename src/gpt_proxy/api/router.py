"""Main API router with ChatGPT backend proxy."""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response, StreamingResponse
from logging import getLogger

from gpt_proxy.services.auth_manager import get_auth_manager
from gpt_proxy.core.chatgpt_client import chatgpt_request, chatgpt_stream

logger = getLogger(__name__)
router = APIRouter()


async def get_access_token(request: Request) -> str:
    """Extract and validate session ID from request, return access token."""
    auth_header = request.headers.get("Authorization", "")

    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Missing Authorization header. Login at /auth/login first.",
                    "type": "authentication_error",
                    "code": "missing_auth",
                }
            },
        )

    session_id = auth_header[7:]  # Remove "Bearer " prefix
    auth_manager = get_auth_manager()

    access_token = await auth_manager.get_valid_token(session_id)
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "message": "Session expired or invalid. Please login again at /auth/login",
                    "type": "authentication_error",
                    "code": "session_expired",
                }
            },
        )

    return access_token


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxy chat completions to ChatGPT backend."""
    import json

    access_token = await get_access_token(request)
    body = await request.body()

    # Check if streaming
    try:
        data = json.loads(body)
        stream = data.get("stream", False)
    except Exception:
        stream = False

    if stream:
        # Streaming response
        async def stream_generator():
            async for chunk in chatgpt_stream(
                access_token=access_token,
                method="POST",
                path="/chat/completions",
                body=body,
            ):
                yield chunk

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    else:
        # Non-streaming
        response = await chatgpt_request(
            access_token=access_token,
            method="POST",
            path="/chat/completions",
            body=body,
        )
        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
        )


@router.get("/v1/models")
async def list_models(request: Request):
    """List available models."""
    access_token = await get_access_token(request)

    response = await chatgpt_request(
        access_token=access_token,
        method="GET",
        path="/models",
        stream=False,
    )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers),
    )


# Catch-all for other endpoints
@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(request: Request, path: str):
    """Catch-all proxy for other ChatGPT backend endpoints."""
    access_token = await get_access_token(request)

    body = await request.body() if request.method in ["POST", "PUT"] else None

    response = await chatgpt_request(
        access_token=access_token,
        method=request.method,
        path=f"/{path}",
        body=body,
        stream=False,
    )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=dict(response.headers),
    )
