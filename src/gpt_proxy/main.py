"""FastAPI application factory."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from gpt_proxy.config import settings
from gpt_proxy.core.openai_client import close_openai_client
from gpt_proxy.api.router import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown
    await close_openai_client()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="Local ChatGPT reverse proxy with API key management",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Health check endpoints (must be before API router)
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": "0.1.0"}

    @app.get("/ready")
    async def readiness_check():
        has_keys = bool(settings.openai_api_keys)
        return {"status": "ready" if has_keys else "not_ready", "has_api_keys": has_keys}

    # Include API router (includes catch-all)
    app.include_router(api_router)

    return app


# Default app instance
app = create_app()
