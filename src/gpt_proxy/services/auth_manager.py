"""Authentication manager for ChatGPT session tokens."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, Literal
import base64
import httpx
import secrets
import asyncio
from logging import getLogger
import json
from pathlib import Path

from gpt_proxy.config import settings

logger = getLogger(__name__)


def utcnow() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


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

    CHATGPT_API_BASE = "https://chatgpt.com"
    SESSION_API = f"{CHATGPT_API_BASE}/api/auth/session"
    BACKEND_API = f"{CHATGPT_API_BASE}/backend-api"
    SESSION_FILE = Path("./sessions.json")

    def __init__(self):
        self.sessions: dict[str, UserSession] = {}
        self._lock = asyncio.Lock()
        self._client: httpx.AsyncClient | None = None
        self._load_sessions()

    def _load_sessions(self):
        """Load sessions from disk."""
        if self.SESSION_FILE.exists():
            try:
                with open(self.SESSION_FILE) as f:
                    data = json.load(f)
                    for sid, sdata in data.items():
                        # Parse datetime, handling both naive and aware formats
                        expires_at_str = sdata["expires_at"]
                        created_at_str = sdata["created_at"]

                        try:
                            expires_at = datetime.fromisoformat(expires_at_str)
                            created_at = datetime.fromisoformat(created_at_str)
                        except ValueError:
                            # Fallback for old format
                            expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))

                        # Ensure timezone-aware
                        if expires_at.tzinfo is None:
                            expires_at = expires_at.replace(tzinfo=timezone.utc)
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=timezone.utc)

                        sdata["expires_at"] = expires_at
                        sdata["created_at"] = created_at
                        # Decode base64-encoded sensitive fields
                        try:
                            sdata["access_token"] = base64.b64decode(sdata["access_token"]).decode()
                            sdata["session_token"] = base64.b64decode(sdata["session_token"]).decode()
                        except Exception:
                            # Legacy plain-text format, use as-is
                            pass
                        self.sessions[sid] = UserSession(**sdata)
                logger.info(f"Loaded {len(self.sessions)} sessions from disk")
            except Exception as e:
                logger.warning(f"Failed to load sessions: {e}")

    def _save_sessions(self):
        """Save sessions to disk."""
        try:
            data = {}
            for sid, session in self.sessions.items():
                if session.is_active:
                    data[sid] = {
                        "session_id": session.session_id,
                        "user_id": session.user_id,
                        "email": session.email,
                        "access_token": base64.b64encode(session.access_token.encode()).decode(),
                        "session_token": base64.b64encode(session.session_token.encode()).decode(),
                        "expires_at": session.expires_at.isoformat(),
                        "created_at": session.created_at.isoformat(),
                        "request_count": session.request_count,
                        "is_active": session.is_active,
                    }
            with open(self.SESSION_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save sessions: {e}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with proxy support."""
        if self._client is None or self._client.is_closed:
            client_kwargs = {
                "timeout": httpx.Timeout(settings.http_timeout, connect=settings.http_connect_timeout),
                "follow_redirects": True,
            }
            if settings.browser_proxy:
                client_kwargs["proxy"] = settings.browser_proxy
                logger.info(f"AuthManager using proxy: {settings.browser_proxy}")
            self._client = httpx.AsyncClient(**client_kwargs)
        return self._client

    def _is_cloudflare_challenge(self, response: httpx.Response) -> bool:
        """Detect if response is a Cloudflare challenge page."""
        if response.status_code in [403, 503]:
            body = response.text or ""
            indicators = [
                "cloudflare",
                "cf-browser-verification",
                "challenge-platform",
                "Just a moment...",
                "Checking your browser",
            ]
            return any(indicator.lower() in body.lower() for indicator in indicators)
        return False

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

            logger.debug(f"Session API response: status={response.status_code}")

            # Check for Cloudflare challenge
            if self._is_cloudflare_challenge(response):
                logger.error("Cloudflare challenge detected. Session may need browser refresh.")
                return None

            if response.status_code != 200:
                body_preview = response.text[:500] if response.text else "<empty>"
                logger.warning(f"Session token exchange failed: status={response.status_code}, body={body_preview}")
                return None

            # Check content type before parsing
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                body_preview = response.text[:500] if response.text else "<empty>"
                logger.error(f"Unexpected content type: {content_type}, body={body_preview}")
                return None

            # Safely parse JSON
            try:
                data = response.json()
            except json.JSONDecodeError as json_error:
                body_preview = response.text[:500] if response.text else "<empty>"
                logger.error(f"JSON parse error: {json_error}, body={body_preview}")
                return None

            if not data.get("accessToken"):
                logger.warning("No accessToken in response")
                return None

            session_id = secrets.token_urlsafe(32)
            user = data.get("user", {})

            # Parse expiry time
            expires_str = data.get("expires", "")
            try:
                expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
            except Exception:
                expires_at = utcnow() + timedelta(hours=1)

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

        except httpx.TimeoutException as e:
            logger.error(f"Timeout exchanging session token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error exchanging session token: {e}")
            return None

    async def validate_session_token(self, session_token: str) -> dict:
        """Validate session token and return basic info without full exchange.

        Returns:
            dict with keys: valid (bool), error (str|None), user_email (str|None)
        """
        client = await self._get_client()

        try:
            response = await client.get(
                self.SESSION_API,
                headers={
                    "Cookie": f"__Secure-next-auth.session-token={session_token}",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                },
            )

            if self._is_cloudflare_challenge(response):
                return {"valid": False, "error": "cloudflare_challenge"}

            if response.status_code == 401:
                return {"valid": False, "error": "invalid_token"}

            if response.status_code != 200:
                return {"valid": False, "error": f"http_{response.status_code}"}

            try:
                data = response.json()
                if data.get("user"):
                    return {
                        "valid": True,
                        "error": None,
                        "user_email": data["user"].get("email"),
                    }
            except json.JSONDecodeError:
                return {"valid": False, "error": "invalid_response"}

            return {"valid": False, "error": "no_user_data"}

        except httpx.TimeoutException:
            return {"valid": False, "error": "timeout"}
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return {"valid": False, "error": str(e)}

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
        self._save_sessions()
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
        if utcnow() >= session.expires_at - timedelta(minutes=5):
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
