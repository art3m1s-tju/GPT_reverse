"""Global error handling."""

from fastapi import Request
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger("gpt_proxy")


class ProxyError(Exception):
    """Custom proxy error."""

    def __init__(self, message: str, code: str, status_code: int = 500, error_type: str = "proxy_error"):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(message)


class UpstreamError(ProxyError):
    """Error from upstream OpenAI API."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(
            message=message,
            code="upstream_error",
            status_code=status_code,
            error_type="upstream_error",
        )


class RateLimitError(ProxyError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            code="rate_limit_exceeded",
            status_code=429,
            error_type="rate_limit_error",
        )


async def proxy_error_handler(request: Request, exc: ProxyError) -> JSONResponse:
    """Handle ProxyError exceptions."""
    logger.error(f"Proxy error: {exc.message} (code={exc.code})")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "type": exc.error_type,
                "code": exc.code,
            }
        },
    )


async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle generic exceptions."""
    from fastapi import HTTPException

    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    logger.exception(f"Unexpected error: {exc}")

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "internal_error",
                "code": "internal_error",
            }
        },
    )
