"""Rate limiting middleware."""

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse
import time
from collections import defaultdict


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting with configurable limits."""

    SKIP_PATHS = {"/health", "/ready", "/docs", "/redoc", "/openapi.json"}

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rpm = requests_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        # Skip rate limit for health endpoints
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"
        client_id = request.headers.get("X-Client-ID", client_ip)

        # Check rate limit
        now = time.time()
        timestamps = self.requests[client_id]

        # Remove old timestamps (older than 1 minute)
        timestamps[:] = [t for t in timestamps if now - t < 60]

        if len(timestamps) >= self.rpm:
            # Calculate retry-after
            oldest = min(timestamps)
            retry_after = int(60 - (now - oldest)) + 1

            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": f"Rate limit exceeded. Max {self.rpm} requests per minute.",
                        "type": "rate_limit_error",
                        "code": "rate_limit_exceeded",
                    }
                },
                headers={"Retry-After": str(retry_after), "X-RateLimit-Limit": str(self.rpm)},
            )

        # Record request
        self.requests[client_id].append(now)

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        remaining = self.rpm - len(self.requests[client_id])
        response.headers["X-RateLimit-Limit"] = str(self.rpm)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
