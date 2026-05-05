"""Main API router with all OpenAI endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import Response, StreamingResponse
import json

from gpt_proxy.core.proxy import proxy_request

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Proxy chat completions to OpenAI."""
    body = await request.body()
    headers = dict(request.headers)

    # Check if streaming is requested
    try:
        data = json.loads(body)
        stream = data.get("stream", False)
    except json.JSONDecodeError:
        stream = False

    result = await proxy_request(
        method="POST",
        path="/v1/chat/completions",
        headers=headers,
        body=body,
        stream=stream,
    )

    if stream:
        return StreamingResponse(
            result.stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                **{k: v for k, v in result.headers.items() if k.lower() not in ("content-type",)},
            },
        )
    else:
        return Response(
            content=result.body,
            status_code=result.status_code,
            headers=result.headers,
            media_type="application/json",
        )


@router.post("/v1/embeddings")
async def embeddings(request: Request):
    """Proxy embeddings to OpenAI."""
    body = await request.body()
    headers = dict(request.headers)

    result = await proxy_request(
        method="POST",
        path="/v1/embeddings",
        headers=headers,
        body=body,
        stream=False,
    )

    return Response(
        content=result.body,
        status_code=result.status_code,
        headers=result.headers,
        media_type="application/json",
    )


@router.post("/v1/images/generations")
async def image_generations(request: Request):
    """Proxy image generation to OpenAI."""
    body = await request.body()
    headers = dict(request.headers)

    result = await proxy_request(
        method="POST",
        path="/v1/images/generations",
        headers=headers,
        body=body,
        stream=False,
    )

    return Response(
        content=result.body,
        status_code=result.status_code,
        headers=result.headers,
        media_type="application/json",
    )


@router.post("/v1/audio/speech")
async def audio_speech(request: Request):
    """Proxy text-to-speech to OpenAI."""
    body = await request.body()
    headers = dict(request.headers)

    result = await proxy_request(
        method="POST",
        path="/v1/audio/speech",
        headers=headers,
        body=body,
        stream=False,
    )

    # Audio response is binary, not JSON
    return Response(
        content=result.body,
        status_code=result.status_code,
        headers=result.headers,
        media_type=result.headers.get("content-type", "audio/mpeg"),
    )


@router.post("/v1/audio/transcriptions")
async def audio_transcriptions(request: Request):
    """Proxy speech-to-text to OpenAI."""
    # Handle multipart/form-data
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    headers = dict(request.headers)

    result = await proxy_request(
        method="POST",
        path="/v1/audio/transcriptions",
        headers=headers,
        body=body,
        stream=False,
    )

    return Response(
        content=result.body,
        status_code=result.status_code,
        headers=result.headers,
        media_type="application/json",
    )


@router.post("/v1/audio/translations")
async def audio_translations(request: Request):
    """Proxy audio translation to OpenAI."""
    body = await request.body()
    headers = dict(request.headers)

    result = await proxy_request(
        method="POST",
        path="/v1/audio/translations",
        headers=headers,
        body=body,
        stream=False,
    )

    return Response(
        content=result.body,
        status_code=result.status_code,
        headers=result.headers,
        media_type="application/json",
    )


@router.get("/v1/models")
async def list_models(request: Request):
    """Proxy model listing to OpenAI."""
    headers = dict(request.headers)

    result = await proxy_request(
        method="GET",
        path="/v1/models",
        headers=headers,
        body=None,
        stream=False,
    )

    return Response(
        content=result.body,
        status_code=result.status_code,
        headers=result.headers,
        media_type="application/json",
    )


@router.get("/v1/models/{model_id}")
async def get_model(request: Request, model_id: str):
    """Proxy model retrieval to OpenAI."""
    headers = dict(request.headers)

    result = await proxy_request(
        method="GET",
        path=f"/v1/models/{model_id}",
        headers=headers,
        body=None,
        stream=False,
    )

    return Response(
        content=result.body,
        status_code=result.status_code,
        headers=result.headers,
        media_type="application/json",
    )


@router.post("/v1/moderations")
async def moderations(request: Request):
    """Proxy content moderation to OpenAI."""
    body = await request.body()
    headers = dict(request.headers)

    result = await proxy_request(
        method="POST",
        path="/v1/moderations",
        headers=headers,
        body=body,
        stream=False,
    )

    return Response(
        content=result.body,
        status_code=result.status_code,
        headers=result.headers,
        media_type="application/json",
    )


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all(request: Request, path: str):
    """Catch-all proxy for any other OpenAI endpoints."""
    body = await request.body() if request.method in ["POST", "PUT", "PATCH"] else None
    headers = dict(request.headers)

    result = await proxy_request(
        method=request.method,
        path=f"/{path}",
        headers=headers,
        body=body,
        stream=False,
    )

    return Response(
        content=result.body,
        status_code=result.status_code,
        headers=result.headers,
    )
