import asyncio
from playwright.async_api import async_playwright
from features.submission.portal_session import PortalSession
from shared.config import load_settings

async def test():
    settings = load_settings()
    async with async_playwright() as pw:
        session = PortalSession(settings.portal_username, settings.portal_password, pw, headless=False)
        page = await session.open()
        print("Success — form page reached")
        input("Press Enter to close browser...")
        await session.close()

asyncio.run(test())

