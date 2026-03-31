from __future__ import annotations

import logging

from playwright.async_api import Browser, BrowserContext, Error as PlaywrightError, Page, Playwright

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
        await new_page.click('#button')
        await new_page.wait_for_load_state("domcontentloaded", timeout=300000)
        self._logger.info("Login submitted — current URL: %s", new_page.url)
        return new_page

    async def _navigate_to_form(self, page: Page) -> None:
        await page.wait_for_selector(
            "text=Tenant Registration",
            state="visible",
            timeout=300000,
        )
        await page.hover("text=Tenant Registration")
        await page.click('a[href="addtenantpgverification.htm"]', no_wait_after=True)
        await page.wait_for_selector(
            '[name="ownerFirstName"]',
            state="visible",
            timeout=300000,        # this is 5 minutes
        )
        self._logger.info("Form page loaded — URL: %s", page.url)
