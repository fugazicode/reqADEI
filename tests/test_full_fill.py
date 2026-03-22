# Run order: test_phase1 → test_phase2 → test_phase3_tenant → test_phase4_addresses → test_full_fill
# Do not skip ahead. Each phase depends on the previous one passing.

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import asyncio
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

try:
    from features.submission.portal_session import PortalSession
    from features.submission.form_filler import FormFiller
    from tests.sample_payload import make_sample_payload
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    print("Ensure portal_session.py and form_filler.py are implemented before running this test.")
    raise SystemExit(1)


SAMPLE_IMAGE_PATH = Path("tests/sample_aadhaar.jpg")
if not SAMPLE_IMAGE_PATH.exists():
    print("NOTE: tests/sample_aadhaar.jpg not found.")
    print("The document upload step will be skipped.")
    print("Place any JPG image at that path to test the upload.")
    IMAGE_BYTES = b""
else:
    IMAGE_BYTES = SAMPLE_IMAGE_PATH.read_bytes()
    print(f"Using image: {SAMPLE_IMAGE_PATH} ({len(IMAGE_BYTES)} bytes)")


async def main() -> None:
    load_dotenv()
    username = os.getenv("PORTAL_USERNAME", "")
    password = os.getenv("PORTAL_PASSWORD", "")

    if not username or not password:
        print("ERROR: PORTAL_USERNAME and PORTAL_PASSWORD must be set in .env")
        return

    async with async_playwright() as pw:
        session = PortalSession(username, password, pw)
        try:
            page = await session.open()

            payload = make_sample_payload()
            filler = FormFiller(page, payload)

            print("Starting full form fill...")
            request_number = await filler.fill(IMAGE_BYTES)
            print(f"SUBMISSION SUCCESS — Request Number: {request_number}")
            print("Observe the browser — this is the success page. Note what it looks like for PDF retrieval planning.")

            if request_number == "UNKNOWN":
                print("WARNING — request number not found. Inspect the success page and update the regex.")
        except Exception:
            print("SUBMISSION FAILED")
            traceback.print_exc()
        finally:
            print("Press Enter to close browser...")
            input()
            await session.close()


asyncio.run(main())
