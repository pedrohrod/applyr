"""
Shared browser session — login once, reuse across all scraping and applying.
Avoids repeated logins that trigger bot detection.
"""

from __future__ import annotations
import asyncio
from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright


LINKEDIN_HOME = "https://www.linkedin.com"
GUPY_HOME = "https://portal.gupy.io"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class SharedBrowser:
    """One browser instance shared for the entire run."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._linkedin_ctx: BrowserContext | None = None
        self._gupy_ctx: BrowserContext | None = None
        self._portal_ctx: BrowserContext | None = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        logger.info("Shared browser started")

    async def linkedin_page(self) -> Page:
        if not self._linkedin_ctx:
            self._linkedin_ctx = await self._browser.new_context(user_agent=USER_AGENT)
        return await self._linkedin_ctx.new_page()

    async def gupy_page(self) -> Page:
        if not self._gupy_ctx:
            self._gupy_ctx = await self._browser.new_context(user_agent=USER_AGENT)
        return await self._gupy_ctx.new_page()

    async def portal_page(self) -> Page:
        """Fresh page for external ATS portals (Greenhouse, Lever, …). No login required."""
        if not self._portal_ctx:
            self._portal_ctx = await self._browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 800},
            )
        return await self._portal_ctx.new_page()

    async def login_linkedin(self, email: str, password: str) -> bool:
        page = await self.linkedin_page()
        try:
            await page.goto(f"{LINKEDIN_HOME}/login", wait_until="networkidle")

            if await is_captcha(page):
                logger.warning("CAPTCHA detected on LinkedIn login — waiting 60s before retrying")
                await asyncio.sleep(60)
                await page.reload()
                if await is_captcha(page):
                    logger.error("CAPTCHA still present — aborting LinkedIn login")
                    await page.close()
                    return False

            await page.fill("#username", email)
            await page.fill("#password", password)
            await page.click('[type="submit"]')
            await page.wait_for_url("**/feed**", timeout=15000)
            logger.info("LinkedIn login successful (session will be reused)")
            return True
        except Exception as e:
            logger.error(f"LinkedIn login failed: {e}")
            return False
        finally:
            await page.close()

    async def login_gupy(self, email: str, password: str) -> bool:
        page = await self.gupy_page()
        try:
            await page.goto(f"{GUPY_HOME}/login", wait_until="domcontentloaded")
            await asyncio.sleep(1)
            await page.fill('input[name="email"]', email)
            await page.fill('input[name="password"]', password)
            submit = await page.query_selector('button[type="submit"]')
            if submit:
                await submit.click()
            await asyncio.sleep(3)
            logger.info("Gupy login successful (session will be reused)")
            return True
        except Exception as e:
            logger.error(f"Gupy login failed: {e}")
            return False
        finally:
            await page.close()

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Shared browser closed")


async def is_captcha(page: Page) -> bool:
    """Detect LinkedIn challenge / CAPTCHA pages."""
    url = page.url.lower()
    if any(kw in url for kw in ("checkpoint", "captcha", "challenge", "verify")):
        return True
    for selector in (
        'iframe[src*="recaptcha"]',
        'iframe[src*="captcha"]',
        '[data-test="challenge"]',
        ".challenge-dialog",
    ):
        if await page.query_selector(selector):
            return True
    return False
