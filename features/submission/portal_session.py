from __future__ import annotations

import logging

from playwright.async_api import Browser, Page, Playwright

# Delhi Police Citizen Services Portal
_LOGIN_URL = "https://cctns.delhipolice.gov.in/citizenservices/"
_FORM_URL = "https://cctns.delhipolice.gov.in/citizenservices/"  # TODO: confirm form page URL after login

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
        await page.fill('[name="j_username"]', self._username)
        await page.fill('[name="j_password"]', self._password)
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")
        self._logger.info("Login submitted — current URL: %s", page.url)

    async def _navigate_to_form(self, page: Page) -> None:
        await page.goto(_FORM_URL, wait_until="networkidle")
        self._logger.info("Navigated to form — current URL: %s", page.url)
