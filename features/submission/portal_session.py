from __future__ import annotations

import logging
import time

from playwright.async_api import Browser, BrowserContext, Error as PlaywrightError, Page, Playwright

_LOGIN_POLL_INTERVAL_S = 0.3
_LOGIN_WAIT_MAX_S = 300.0

# Delhi Police Citizen Services Portal
_LOGIN_URL = "https://cctns.delhipolice.gov.in/citizenservices/"

LOGGER = logging.getLogger(__name__)


class PortalSession:
    def __init__(
        self,
        username: str,
        password: str,
        playwright: Playwright,
        *,
        headless: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._pw = playwright
        self._headless = headless
        self._logger = logger or LOGGER
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def open(self) -> Page:
        self._browser = await self._pw.chromium.launch(headless=self._headless)
        # accept_downloads=True is required for expect_download() to work.
        # Without it Playwright silently cancels every download and the event
        # never fires, regardless of whether it originates from the current page
        # or a tab opened via window.open().
        self._context = await self._browser.new_context(accept_downloads=True)
        page = await self._context.new_page()
        new_page = await self._login(page)
        await self._navigate_to_form(new_page)
        return new_page

    async def close(self) -> None:
        if self._browser:
            try:
                await self._browser.close()
            except PlaywrightError:
                pass
            self._browser = None
            self._context = None

    async def _login(self, page: Page) -> Page:
        await page.goto("https://delhipolice.gov.in/", wait_until="domcontentloaded")
        await page.wait_for_selector("text=Domestic Help/Tenant Registration", state="visible", timeout=300000)
        async with page.context.expect_page() as new_page_info:
            await page.click("text=Domestic Help/Tenant Registration")
        new_page = await new_page_info.value
        await new_page.wait_for_selector('[name="j_username"]', state="visible", timeout=300000)
        await new_page.click('[name="j_username"]')
        await new_page.fill('[name="j_username"]', self._username)
        await new_page.click('[name="j_password"]')
        await new_page.fill('[name="j_password"]', self._password)
        async with new_page.expect_navigation(timeout=300_000):
            await new_page.click("#button")
        await new_page.wait_for_load_state("load", timeout=300_000)
        # domcontentloaded alone can win a redirect race; wait until we see either
        # failure (login.htm) or a CCTNS citizen-services URL.
        deadline = time.monotonic() + _LOGIN_WAIT_MAX_S
        while time.monotonic() < deadline:
            url = new_page.url
            lower = url.casefold()
            if "login.htm" in lower:
                raise RuntimeError(
                    "Portal login failed — credentials rejected. "
                    f"Current URL: {url}. Check PORTAL_USERNAME / PORTAL_PASSWORD."
                )
            if "citizenservices" in lower or "cctns.delhipolice" in lower:
                self._logger.info("Login succeeded — current URL: %s", url)
                return new_page
            await new_page.wait_for_timeout(int(_LOGIN_POLL_INTERVAL_S * 1000))
        raise RuntimeError(
            "Portal login timed out waiting for CCTNS after submit. "
            f"Last URL: {new_page.url}. Check PORTAL_USERNAME / PORTAL_PASSWORD."
        )

    async def _navigate_to_form(self, page: Page) -> None:
        await page.goto(
            "https://cctns.delhipolice.gov.in/citizenservices/addtenantpgverification.htm",
            wait_until="domcontentloaded",
            timeout=300000,
        )
        nav_url = page.url.casefold()
        if "login.htm" in nav_url:
            raise RuntimeError(
                "Portal session invalid or expired — landed on login page instead of tenant form. "
                f"Current URL: {page.url}"
            )
        if "citizenservices" not in nav_url:
            raise RuntimeError(
                "Unexpected URL after opening tenant form (expected CCTNS citizen services). "
                f"Current URL: {page.url}"
            )
        await page.wait_for_selector(
            '[name="ownerFirstName"]',
            state="visible",
            timeout=300000,        # this is 5 minutes
        )
        self._logger.info("Form page loaded — URL: %s", page.url)
