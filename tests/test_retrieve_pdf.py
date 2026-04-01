"""
Isolated PDF retrieval test.

Purpose
-------
Verify that, given a known request number, the bot can:
  1. Log into the Delhi Police CCTNS portal
  2. Navigate to the "View Tenant Registration Detail" page
  3. Download the generated PDF for that request number
  4. Apply the PREVIEW watermark to the downloaded bytes

This test does NOT trigger main.py or the Telegram bot.  It reuses the same
PortalSession / FormFiller classes that the live SubmissionWorker uses, so the
session lifecycle here is identical to the real end-to-end flow.

Note on session.open()
----------------------
PortalSession.open() navigates all the way to the form-filling page
(addtenantpgverification.htm) after login.  _retrieve_pdf() then navigates
*away* from that page to the "View Tenant Registration Detail" page.  This is
intentional — the session only needs to be authenticated; the starting page
does not matter for retrieval.

Usage
-----
  python -m tests.test_retrieve_pdf

Required environment variables (.env or shell):
  PORTAL_USERNAME
  PORTAL_PASSWORD
"""

import asyncio
import os
import pathlib
import sys
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from playwright.async_api import async_playwright

try:
    from features.submission.portal_session import PortalSession
    from features.submission.form_filler import FormFiller
    from tests.sample_payload import make_sample_payload
    from utils.watermark import apply_watermark
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    print("Ensure all dependencies are installed and PYTHONPATH is set correctly.")
    raise SystemExit(1)

# ── Test configuration ────────────────────────────────────────────────────────
# Replace with a real request number from a previous submission to test against
# the live portal.
REQUEST_NUMBER = "816726116865"

MAX_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = 10

# Run headless so the test can be executed in CI or without a display.
# Set to False locally if you want to watch the browser navigate.
HEADLESS = True
# ─────────────────────────────────────────────────────────────────────────────


async def main() -> None:
    load_dotenv()
    username = os.getenv("PORTAL_USERNAME", "")
    password = os.getenv("PORTAL_PASSWORD", "")

    if not username or not password:
        print("ERROR: PORTAL_USERNAME and PORTAL_PASSWORD must be set in .env")
        return

    async with async_playwright() as pw:
        # headless=True keeps the test self-contained; no display required.
        session = PortalSession(username, password, pw, headless=HEADLESS)
        try:
            # open() logs in and navigates to the form page.  _retrieve_pdf()
            # will navigate away from the form page to the retrieval page, so
            # the exact landing page after open() does not matter.
            page = await session.open()
            print(f"Portal authenticated — current URL: {page.url}")

            # FormFiller is instantiated only because _retrieve_pdf() is an
            # instance method on it.  The payload is not used during retrieval.
            payload = make_sample_payload()
            filler = FormFiller(page, payload)

            # ── RETRIEVAL BLOCK WITH RETRY ────────────────────────────────────
            result = b""
            retrieval_pass = False

            for attempt in range(1, MAX_ATTEMPTS + 1):
                print(f"\nRetrieval attempt {attempt} of {MAX_ATTEMPTS}...")
                result = await filler._retrieve_pdf(REQUEST_NUMBER)
                print(f"  Returned {len(result)} bytes")
                print(f"  Magic bytes: {result[:4]}")
                if len(result) > 1000 and result[:4] == b"%PDF":
                    retrieval_pass = True
                    break
                print(f"  Attempt {attempt} did not return a real PDF.")
                if attempt < MAX_ATTEMPTS:
                    print(f"  Waiting {RETRY_SLEEP_SECONDS}s before retry...")
                    await asyncio.sleep(RETRY_SLEEP_SECONDS)

            if retrieval_pass:
                print(f"\nRETRIEVAL — PASS ({len(result)} bytes)")
            else:
                print(f"\nRETRIEVAL — FAIL after {MAX_ATTEMPTS} attempts")
                print(f"  Final result length: {len(result)} bytes")
                print(f"  First 200 bytes: {result[:200]}")
                print("  Diagnosis: if length is 273, _retrieve_pdf fell back to")
                print("  _DUMMY_PDF_BYTES on every attempt — the portal navigation")
                print("  or download step failed. Check the WARNING logs above.")

            # ── WATERMARK BLOCK ───────────────────────────────────────────────
            print("\nRunning watermark check...")
            try:
                watermarked = apply_watermark(result)
                watermark_pass = (
                    watermarked[:4] == b"%PDF"
                    and len(watermarked) > len(result)
                )
                if watermark_pass:
                    print(f"WATERMARK — PASS ({len(watermarked)} bytes)")
                else:
                    print("WATERMARK — FAIL")
                    print(f"  watermarked length : {len(watermarked)}")
                    print(f"  original length    : {len(result)}")
                    print(f"  First 4 bytes      : {watermarked[:4]}")
                    print("  Diagnosis: apply_watermark hit an internal exception")
                    print("  and returned original bytes unchanged.")
            except Exception:
                watermark_pass = False
                print("WATERMARK — FAIL (exception during apply_watermark)")
                traceback.print_exc()

            # ── OVERALL VERDICT ───────────────────────────────────────────────
            print()
            if retrieval_pass and watermark_pass:
                print("OVERALL — PASS")
            else:
                print("OVERALL — FAIL")

        except Exception:
            print("\nEXCEPTION during test setup or execution")
            traceback.print_exc()
        finally:
            await session.close()


if __name__ == "__main__":
    asyncio.run(main())
