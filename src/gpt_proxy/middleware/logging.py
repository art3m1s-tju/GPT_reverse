"""Request/response logging middleware."""

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
import json
import time
import uuid
import logging

logger = logging.getLogger("gpt_proxy")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses."""

    SKIP_PATHS = {"/health", "/ready", "/docs", "/redoc", "/openapi.json"}
    MAX_BODY_LOG = 1000  # Max characters to log for body

    async def dispatch(self, request: Request, call_next):
        # Skip logging for health endpoints
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        start_time = time.time()
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Log request
        log_data = {
            "event": "request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params),
            "client": request.client.host if request.client else None,
        }
        logger.info(json.dumps(log_data))

        # Process request
        response = await call_next(request)

        # Log response
        duration = time.time() - start_time
        log_data = {
            "event": "response",
            "request_id": request_id,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
        }
        logger.info(json.dumps(log_data))

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response
