from __future__ import annotations

import logging

from playwright.async_api import Browser, Page, Playwright

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

    async def open(self) -> Page:
        self._browser = await self._pw.firefox.launch(headless=self._headless)
        page = await self._browser.new_page()
        await self._login(page)
        await self._navigate_to_form(page)
        return page

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None

    async def _login(self, page: Page) -> None:
        await page.goto(_LOGIN_URL, wait_until="networkidle")
        await page.click('[name="j_username"]')
        await page.fill('[name="j_username"]', self._username)

        await page.click('[name="j_password"]')
        await page.fill('[name="j_password"]', self._password)
        await page.click('#button')
        await page.wait_for_load_state("networkidle")
        self._logger.info("Login submitted — current URL: %s", page.url)

    async def _navigate_to_form(self, page: Page) -> None:
        # Wait for the dashboard to confirm login succeeded
        await page.wait_for_selector(
            "text=Tenant Registration",
            timeout=30000,
        )
        self._logger.info("Dashboard loaded — navigating to form")

        # Navigate through the menu rather than direct goto
        await page.hover("text=Tenant Registration")
        await page.wait_for_selector(
            "text=Add Tenant/PG",
            state="visible",
            timeout=10000,
        )
        await page.click("text=Add Tenant/PG")

        # Wait for the form to fully load
        await page.wait_for_selector(
            '[name="ownerFirstName"]',
            state="visible",
            timeout=30000,
        )
        self._logger.info("Form page loaded — URL: %s", page.url)
