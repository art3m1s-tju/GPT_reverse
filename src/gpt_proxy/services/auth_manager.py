"""Authentication manager for ChatGPT session tokens."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Literal
import httpx
import secrets
import asyncio
from logging import getLogger

logger = getLogger(__name__)


@dataclass
class UserSession:
    """User session with ChatGPT tokens."""
    session_id: str
    user_id: str
    email: str
    access_token: str
    session_token: str  # ChatGPT session token (from browser)
    expires_at: datetime
    created_at: datetime = field(default_factory=datetime.now)
    request_count: int = 0
    is_active: bool = True


class AuthManager:
    """Manage ChatGPT session-based authentication."""

    CHATGPT_API_BASE = "https://chat.openai.com"
    SESSION_API = f"{CHATGPT_API_BASE}/api/auth/session"
    BACKEND_API = f"{CHATGPT_API_BASE}/backend-api"

    def __init__(self):
        self.sessions: dict[str, UserSession] = {}
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    async def exchange_session_token(self, session_token: str) -> Optional[UserSession]:
        """Exchange ChatGPT session token for access token.

        Args:
            session_token: The __Secure-next-auth.session-token from browser

        Returns:
            UserSession if successful, None otherwise
        """
        client = await self._get_client()

        try:
            response = await client.get(
                self.SESSION_API,
                headers={
                    "Cookie": f"__Secure-next-auth.session-token={session_token}",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                logger.warning(f"Session token exchange failed: {response.status_code}")
                return None

            data = response.json()

            if not data.get("accessToken"):
                logger.warning("No accessToken in response")
                return None

            session_id = secrets.token_urlsafe(32)
            user = data.get("user", {})

            # Parse expiry time
            expires_str = data.get("expires", "")
            try:
                expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            except:
                expires_at = datetime.now() + timedelta(hours=1)

            session = UserSession(
                session_id=session_id,
                user_id=user.get("id", "unknown"),
                email=user.get("email", "unknown"),
                access_token=data["accessToken"],
                session_token=session_token,
                expires_at=expires_at,
            )

            logger.info(f"Created session for user: {session.email}")
            return session

        except Exception as e:
            logger.error(f"Error exchanging session token: {e}")
            return None

    async def refresh_session(self, session_id: str) -> bool:
        """Refresh expired access token using session token.

        Args:
            session_id: The session ID to refresh

        Returns:
            True if refreshed successfully
        """
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False

            # Re-exchange session token
            new_session = await self.exchange_session_token(session.session_token)
            if new_session:
                new_session.session_id = session_id  # Keep same ID
                new_session.request_count = session.request_count
                self.sessions[session_id] = new_session
                logger.info(f"Refreshed session for: {session.email}")
                return True

            return False

    def create_session(self, session: UserSession) -> str:
        """Store session and return ID."""
        self.sessions[session.session_id] = session
        return session.session_id

    def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get session by ID."""
        return self.sessions.get(session_id)

    async def get_valid_token(self, session_id: str) -> Optional[str]:
        """Get valid access token, refreshing if needed.

        Args:
            session_id: The session ID

        Returns:
            Valid access token or None
        """
        session = self.sessions.get(session_id)
        if not session or not session.is_active:
            return None

        # Check if token is expired or about to expire (5 min buffer)
        if datetime.now() >= session.expires_at - timedelta(minutes=5):
            # Try to refresh
            if not await self.refresh_session(session_id):
                return None
            session = self.sessions.get(session_id)

        session.request_count += 1
        return session.access_token if session else None

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        if session_id in self.sessions:
            self.sessions[session_id].is_active = False
            return True
        return False

    def list_sessions(self) -> list[dict]:
        """List all active sessions (masked)."""
        return [
            {
                "session_id": s.session_id[:8] + "...",
                "email": s.email,
                "is_active": s.is_active,
                "request_count": s.request_count,
                "expires_at": s.expires_at.isoformat(),
            }
            for s in self.sessions.values()
        ]

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Global auth manager instance
_auth_manager: AuthManager | None = None


def get_auth_manager() -> AuthManager:
    """Get the global auth manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


async def close_auth_manager():
    """Close the global auth manager."""
    global _auth_manager
    if _auth_manager:
        await _auth_manager.close()
