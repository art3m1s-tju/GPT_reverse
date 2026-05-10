"""Browser-based authentication for ChatGPT using Playwright."""

from playwright.async_api import async_playwright, BrowserContext
from typing import Optional
from pathlib import Path
from logging import getLogger
import asyncio
import os

logger = getLogger(__name__)


class BrowserAuthManager:
    """Manage browser-based ChatGPT authentication with persistent profile."""

    CHATGPT_URL = "https://chatgpt.com/auth/login"
    SESSION_COOKIE_NAME = "__Secure-next-auth.session-token"

    def __init__(self, profile_dir: str = "./browser_profile", proxy: str = None):
        self.profile_dir = Path(profile_dir)
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        # 代理设置，从环境变量或参数获取
        self.proxy = proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")

    async def initialize(self, headless: bool = False):
        """Initialize browser context with persistent profile.

        Args:
            headless: If False, shows browser window for user interaction
        """
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()

        launch_options = {
            "user_data_dir": str(self.profile_dir),
            "headless": headless,
            "channel": "chrome",
            "viewport": {"width": 1280, "height": 800},
            "locale": "en-US",
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
            ],
            "ignore_default_args": ["--enable-automation"],
        }

        # 添加代理支持
        if self.proxy:
            logger.info(f"Using proxy: {self.proxy}")
            launch_options["proxy"] = {"server": self.proxy}

        try:
            self._context = await self._playwright.chromium.launch_persistent_context(**launch_options)
        except Exception as e:
            logger.warning(f"Failed to launch with channel='chrome' ({e}); falling back to bundled Chromium")
            launch_options.pop("channel", None)
            self._context = await self._playwright.chromium.launch_persistent_context(**launch_options)

        # 抹掉 navigator.webdriver 等自动化指纹
        await self._context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = window.chrome || { runtime: {} };
            const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
            if (originalQuery) {
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications'
                        ? Promise.resolve({ state: Notification.permission })
                        : originalQuery(parameters)
                );
            }
            """
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
            await page.goto(self.CHATGPT_URL, wait_until="domcontentloaded", timeout=60000)

            # Check if already logged in
            cookies = await self._context.cookies()
            for cookie in cookies:
                if cookie["name"] == self.SESSION_COOKIE_NAME:
                    logger.info("Found existing session token")
                    return cookie["value"]

            if wait_for_login:
                logger.info(f"Waiting for user to login (timeout: {timeout}s)...")
                # 轮询 cookie，避免依赖 URL 模式（不同域名/路径都可能出现）
                deadline = asyncio.get_event_loop().time() + timeout
                while asyncio.get_event_loop().time() < deadline:
                    cookies = await self._context.cookies()
                    for cookie in cookies:
                        if cookie["name"] == self.SESSION_COOKIE_NAME and cookie.get("value"):
                            logger.info("Successfully extracted session token")
                            return cookie["value"]
                    await asyncio.sleep(2)

                logger.warning("Login timeout: session cookie not found")
                return None

            return None

        except Exception as e:
            logger.error(f"Browser error: {e}")
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
    from gpt_proxy.config import settings

    # 每次都重新创建，确保使用最新配置
    if _browser_auth is None:
        _browser_auth = BrowserAuthManager(
            profile_dir=settings.browser_profile_dir,
            proxy=settings.browser_proxy or None
        )

    # 确保代理设置正确
    if settings.browser_proxy and _browser_auth.proxy != settings.browser_proxy:
        _browser_auth.proxy = settings.browser_proxy
        logger.info(f"Updated proxy to: {settings.browser_proxy}")

    return _browser_auth


async def close_browser_auth():
    """Close the global browser auth instance."""
    global _browser_auth
    if _browser_auth:
        await _browser_auth.close()
        _browser_auth = None
