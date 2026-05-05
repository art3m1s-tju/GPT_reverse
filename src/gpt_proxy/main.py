"""FastAPI application factory."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from gpt_proxy.config import settings
from gpt_proxy.services.auth_manager import close_auth_manager
from gpt_proxy.services.browser_auth import close_browser_auth
from gpt_proxy.api.router import router as api_router
from gpt_proxy.api.auth_router import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown
    await close_auth_manager()
    await close_browser_auth()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="GPT Reverse Proxy",
        description="""
## ChatGPT Reverse Proxy

Use ChatGPT without API keys! Login with your ChatGPT account session token.

### Quick Start

1. **Get session token**: Login to chat.openai.com, open DevTools, copy `__Secure-next-auth.session-token` cookie
2. **Login**: POST to `/auth/login` with your session token
3. **Use API**: Use the returned `session_id` as Bearer token

### Example

```bash
# Login
curl -X POST http://localhost:8000/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"session_token": "your-token-here"}'

# Chat
curl -X POST http://localhost:8000/v1/chat/completions \\
  -H "Authorization: Bearer <session_id>" \\
  -H "Content-Type: application/json" \\
  -d '{"model": "gpt-4", "messages": [{"role": "user", "content": "Hello!"}]}'
```
""",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Health check endpoints
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": "0.2.0"}

    @app.get("/ready")
    async def readiness_check():
        return {"status": "ready"}

    # Include routers
    app.include_router(auth_router)
    app.include_router(api_router)

    return app


# Default app instance
app = create_app()
