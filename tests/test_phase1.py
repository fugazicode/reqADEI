# Run order: test_phase1 → test_phase2 → test_phase3_tenant → test_phase4_addresses → test_full_fill
# Do not skip ahead. Each phase depends on the previous one passing.

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import asyncio
import os
import traceback

from dotenv import load_dotenv
from playwright.async_api import async_playwright

try:
    from features.submission.portal_session import PortalSession
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    print("portal_session.py must be implemented before running this test.")
    raise SystemExit(1)


async def main() -> None:
    load_dotenv()
    username = os.getenv("PORTAL_USERNAME", "")
    password = os.getenv("PORTAL_PASSWORD", "")

    if not username or not password:
        print("ERROR: PORTAL_USERNAME and PORTAL_PASSWORD must be set in .env")
        return

    print(f"Attempting login as: {username}")

    async with async_playwright() as pw:
        session = PortalSession(username, password, pw)
        try:
            page = await session.open()
            print("SUCCESS — form page reached")
            print(f"URL: {page.url}")
        except Exception:
            print("FAILED")
            traceback.print_exc()
        finally:
            print("Press Enter to close browser...")
            input()
            await session.close()


asyncio.run(main())
