"""Browser-based authentication for ChatGPT using Playwright."""

from playwright.async_api import async_playwright, BrowserContext
from typing import Optional
from pathlib import Path
from logging import getLogger
import asyncio

logger = getLogger(__name__)


class BrowserAuthManager:
    """Manage browser-based ChatGPT authentication with persistent profile."""

    CHATGPT_URL = "https://chat.openai.com"
    SESSION_COOKIE_NAME = "__Secure-next-auth.session-token"

    def __init__(self, profile_dir: str = "./browser_profile"):
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._context: Optional[BrowserContext] = None

    async def initialize(self, headless: bool = False):
        """Initialize browser context with persistent profile.

        Args:
            headless: If False, shows browser window for user interaction
        """
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            str(self.profile_dir),
            headless=headless,
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
        )
        logger.info(f"Browser initialized with profile: {self.profile_dir}")

    async def get_session_token(
        self,
        wait_for_login: bool = True,
        timeout: int = 300
    ) -> Optional[str]:
        """Get session token from browser.

        Args:
            wait_for_login: Wait for user to complete login
            timeout: Maximum seconds to wait for login

        Returns:
            Session token or None
        """
        if not self._context:
            await self.initialize(headless=False)

        page = await self._context.new_page()

        try:
            logger.info("Navigating to ChatGPT...")
            await page.goto(self.CHATGPT_URL, wait_until="networkidle")

            # Check if already logged in
            cookies = await self._context.cookies()
            for cookie in cookies:
                if cookie["name"] == self.SESSION_COOKIE_NAME:
                    logger.info("Found existing session token")
                    return cookie["value"]

            if wait_for_login:
                logger.info("Waiting for user to login...")
                # Wait for redirect to chat page (indicates successful login)
                try:
                    await page.wait_for_url("**/chat*", timeout=timeout * 1000)
                except Exception:
                    logger.warning("Login timeout or cancelled")
                    return None

                # Extract session token after login
                cookies = await self._context.cookies()
                for cookie in cookies:
                    if cookie["name"] == self.SESSION_COOKIE_NAME:
                        logger.info("Successfully extracted session token")
                        return cookie["value"]

            return None

        except Exception as e:
            logger.error(f"Error getting session token: {e}")
            return None
        finally:
            await page.close()

    async def close(self):
        """Close browser and cleanup."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Browser closed")


# Singleton instance
_browser_auth: BrowserAuthManager | None = None


def get_browser_auth() -> BrowserAuthManager:
    """Get the global browser auth instance."""
    global _browser_auth
    if _browser_auth is None:
        _browser_auth = BrowserAuthManager()
    return _browser_auth


async def close_browser_auth():
    """Close the global browser auth instance."""
    global _browser_auth
    if _browser_auth:
        await _browser_auth.close()
        _browser_auth = None
