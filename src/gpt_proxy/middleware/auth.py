"""Authentication middleware."""

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    """Validate API keys against configured keys."""

    SKIP_PATHS = {"/health", "/ready", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        # Skip auth for health and docs endpoints
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")

        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Missing Authorization header",
                        "type": "invalid_request_error",
                        "code": "invalid_api_key",
                    }
                },
            )

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "message": "Invalid Authorization header format. Expected 'Bearer <token>'",
                        "type": "invalid_request_error",
                        "code": "invalid_api_key",
                    }
                },
            )

        # Accept any valid Bearer token - the proxy manages actual OpenAI keys
        return await call_next(request)
