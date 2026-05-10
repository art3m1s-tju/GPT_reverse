"""Main API router with ChatGPT backend proxy using conversation endpoint."""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response, StreamingResponse
from logging import getLogger
import json

from gpt_proxy.services.auth_manager import get_auth_manager
from gpt_proxy.core.chatgpt_client import ChatGPTClient
from gpt_proxy.config import settings

logger = getLogger(__name__)
router = APIRouter()


async def get_access_token(request: Request) -> tuple[str, str]:
    """Extract and validate session ID from request, return (access_token, session_id)."""
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

    return access_token, session_id


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxy chat completions to ChatGPT conversation endpoint.

    Converts OpenAI Chat Completions API format to ChatGPT web API format.
    """
    access_token, session_id = await get_access_token(request)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail={"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}},
        )

    model = body.get("model", "gpt-4o-mini")
    messages = body.get("messages", [])
    stream = body.get("stream", False)

    # Optional conversation continuation
    conversation_id = body.get("conversation_id")
    parent_message_id = body.get("parent_message_id")

    if not messages:
        raise HTTPException(
            status_code=400,
            detail={"error": {"message": "messages is required", "type": "invalid_request_error"}},
        )

    # Get proxy from settings
    proxy_url = settings.browser_proxy if settings.browser_proxy else None

    client = ChatGPTClient(
        access_token=access_token,
        proxy_url=proxy_url,
    )

    try:
        result = await client.chat_completions(
            model=model,
            messages=messages,
            stream=stream,
            conversation_id=conversation_id,
            parent_message_id=parent_message_id,
        )

        if stream:
            return StreamingResponse(
                result,
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            return Response(
                content=json.dumps(result),
                media_type="application/json",
            )

    except Exception as e:
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": {"message": str(e), "type": "internal_error"}},
        )
    finally:
        await client.close()


@router.get("/v1/models")
async def list_models(request: Request):
    """List available models."""
    # Return static list of supported models
    models = [
        {"id": "gpt-3.5-turbo", "object": "model", "owned_by": "openai"},
        {"id": "gpt-4", "object": "model", "owned_by": "openai"},
        {"id": "gpt-4-turbo", "object": "model", "owned_by": "openai"},
        {"id": "gpt-4o", "object": "model", "owned_by": "openai"},
        {"id": "gpt-4o-mini", "object": "model", "owned_by": "openai"},
        {"id": "o1", "object": "model", "owned_by": "openai"},
        {"id": "o1-mini", "object": "model", "owned_by": "openai"},
        {"id": "o1-preview", "object": "model", "owned_by": "openai"},
        {"id": "auto", "object": "model", "owned_by": "openai"},
    ]

    return {
        "object": "list",
        "data": models,
    }
