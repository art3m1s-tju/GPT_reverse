"""Pytest configuration and fixtures."""

import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport

from gpt_proxy.main import create_app


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create test client."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def mock_session_token():
    """Mock ChatGPT session token."""
    return "mock-session-token-for-testing"


@pytest.fixture
def mock_auth_response():
    """Mock authentication response from ChatGPT."""
    return {
        "user": {
            "id": "user-123",
            "email": "test@example.com",
            "name": "Test User",
        },
        "accessToken": "mock-access-token-12345",
        "expires": "2025-01-01T00:00:00Z",
    }
