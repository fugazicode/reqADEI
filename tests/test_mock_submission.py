import asyncio
import re
import logging
from playwright.async_api import async_playwright
from tests.mock_portal_server import start_mock_server, stop_mock_server

class MockSubmitter:
    def __init__(self, page):
        self._page = page
        self._logger = logging.getLogger(__name__)

    async def _submit_and_get_result(self) -> str:
        self._page.on("dialog", lambda dialog: asyncio.ensure_future(dialog.dismiss()))

        captured_body: list[str] = []

        async def handle_submit_response(route, request) -> None:
            if request.method != "POST":
                await route.continue_()
                return
            try:
                response = await route.fetch(timeout=0)
                body = await response.text()
                captured_body.append(body)
                await route.fulfill(
                    status=200,
                    content_type="text/html",
                    body="<html><body>OK</body></html>",
                )
            except Exception as exc:
                self._logger.warning(
                    "Route handler failed to fetch response: %s", exc
                )
                await route.continue_()

        await self._page.route(
            "**/addtenantpgverification.htm",
            handle_submit_response,
        )

        await self._page.click("#submit123", no_wait_after=True)

        deadline = 60
        interval = 0.5
        elapsed = 0.0
        while not captured_body and elapsed < deadline:
            await asyncio.sleep(interval)
            elapsed += interval

        if not captured_body:
            self._logger.warning(
                "Route handler did not capture POST response within %ds", deadline
            )

        await self._page.unroute("**/addtenantpgverification.htm")

        if captured_body:
            content = captured_body[0]
        else:
            self._logger.warning(
                "Route handler did not capture response — falling back to page body"
            )
            content = await self._page.inner_text("body")

        self._logger.warning("Response content (first 1000 chars): %s", content[:1000])

        if "Unable to process your request" in content:
            raise RuntimeError("Portal server rejected the submission.")

        match = re.search(
            r"Service\s+Request\s+Number\s+(\d+)",
            content,
            re.IGNORECASE,
        )
        if match:
            return match.group(1)

        match = re.search(r"Request\s+Number[:\s]+(\d+)", content, re.IGNORECASE)
        if match:
            return match.group(1)

        match = re.search(r"(\d{6,})", content)
        if match:
            self._logger.warning(
                "Primary regex did not match — returning first long number: %s",
                match.group(1),
            )
            return match.group(1)

        self._logger.warning("Request number not found in captured response")
        return "UNKNOWN"

async def main():
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(name)s | %(message)s")
    server = start_mock_server()
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.goto("http://localhost:8080/addtenantpgverification.htm", wait_until="domcontentloaded")
            print("Navigated to mock portal")
            submitter = MockSubmitter(page)
            print("Calling _submit_and_get_result — expect ~35s wait")
            result = await submitter._submit_and_get_result()
            if result == "816726116784":
                print("PASS — Request Number:", result)
            else:
                print("FAIL — Request Number:", result)
            await browser.close()
    finally:
        stop_mock_server(server)

if __name__ == "__main__":
    asyncio.run(main())
