"""Authentication API routes."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
import httpx

from gpt_proxy.services.auth_manager import get_auth_manager, AuthManager

router = APIRouter(prefix="/auth", tags=["authentication"])


class SessionTokenLogin(BaseModel):
    """Login with ChatGPT session token."""
    session_token: str


class LoginResponse(BaseModel):
    """Response after successful login."""
    session_id: str
    user_email: str
    expires_at: str
    message: str = "Login successful. Use session_id as Bearer token in API requests."


class SessionInfo(BaseModel):
    """Session information."""
    session_id: str
    email: str
    is_active: bool
    request_count: int
    expires_at: str


class LogoutResponse(BaseModel):
    """Logout response."""
    message: str


def get_auth() -> AuthManager:
    """Dependency to get auth manager."""
    return get_auth_manager()


@router.post("/login", response_model=LoginResponse)
async def login_with_session_token(
    data: SessionTokenLogin,
    auth: AuthManager = Depends(get_auth),
):
    """Login using ChatGPT session token.

    ## How to get session token:

    1. Go to https://chat.openai.com and login
    2. Open browser DevTools (F12)
    3. Go to Application > Cookies > chat.openai.com
    4. Find '__Secure-next-auth.session-token' cookie
    5. Copy its value and paste here

    Or run in browser console:
    ```javascript
    document.cookie.split('; ').find(c => c.startsWith('__Secure-next-auth.session-token='))?.split('=')[1]
    ```
    """
    session = await auth.exchange_session_token(data.session_token)

    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid session token or token expired. Please get a fresh token from chat.openai.com",
        )

    auth.create_session(session)

    return LoginResponse(
        session_id=session.session_id,
        user_email=session.email,
        expires_at=session.expires_at.isoformat(),
    )


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(auth: AuthManager = Depends(get_auth)):
    """List all active sessions."""
    return auth.list_sessions()


@router.post("/logout", response_model=LogoutResponse)
async def logout(session_id: str, auth: AuthManager = Depends(get_auth)):
    """Logout and invalidate session."""
    if auth.invalidate_session(session_id):
        return LogoutResponse(message="Session invalidated successfully")
    raise HTTPException(status_code=404, detail="Session not found")


@router.get("/status")
async def auth_status(auth: AuthManager = Depends(get_auth)):
    """Get authentication system status."""
    sessions = auth.list_sessions()
    active = sum(1 for s in sessions if s["is_active"])
    return {
        "total_sessions": len(sessions),
        "active_sessions": active,
        "status": "operational",
    }


@router.get("/help")
async def auth_help():
    """Get help on how to obtain session token."""
    return {
        "title": "How to get ChatGPT session token",
        "steps": [
            "1. Go to https://chat.openai.com and login with your OpenAI account",
            "2. Open browser DevTools (press F12)",
            "3. Go to Application tab > Cookies > chat.openai.com",
            "4. Find cookie named '__Secure-next-auth.session-token'",
            "5. Copy its value",
            "6. POST to /auth/login with {'session_token': '<your_token>'}",
        ],
        "browser_console_method": "Run this in browser console on chat.openai.com:\n"
        "document.cookie.split('; ').find(c => c.startsWith('__Secure-next-auth.session-token='))?.split('=')[1]",
        "note": "Session tokens expire after some time. You may need to refresh them periodically.",
    }


@router.post("/login/browser", response_model=LoginResponse)
async def login_via_browser(
    timeout: int = 300,
    auth: AuthManager = Depends(get_auth),
):
    """Login via automated browser.

    Opens a browser window for user to login to ChatGPT,
    then automatically extracts session token.

    Args:
        timeout: Maximum seconds to wait for login (default 5 minutes)
    """
    from gpt_proxy.services.browser_auth import get_browser_auth, close_browser_auth

    browser_auth = get_browser_auth()

    try:
        # Get session token from browser
        session_token = await browser_auth.get_session_token(
            wait_for_login=True,
            timeout=timeout
        )

        if not session_token:
            raise HTTPException(
                status_code=401,
                detail="Login failed or timed out. Please try again."
            )

        # Exchange for access token
        session = await auth.exchange_session_token(session_token)
        if not session:
            raise HTTPException(
                status_code=401,
                detail="Failed to exchange session token."
            )

        auth.create_session(session)

        return LoginResponse(
            session_id=session.session_id,
            user_email=session.email,
            expires_at=session.expires_at.isoformat(),
            message="Browser login successful!"
        )
    finally:
        await close_browser_auth()


@router.get("/login/status")
async def check_browser_login_status():
    """Check if user is logged in via browser profile."""
    from gpt_proxy.services.browser_auth import get_browser_auth

    browser_auth = get_browser_auth()
    await browser_auth.initialize(headless=True)

    try:
        session_token = await browser_auth.get_session_token(wait_for_login=False)
        return {
            "logged_in": session_token is not None,
            "message": "Already logged in" if session_token else "Not logged in"
        }
    finally:
        await browser_auth.close()