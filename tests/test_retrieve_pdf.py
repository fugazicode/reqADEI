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

REQUEST_NUMBER = "816726116865"
MAX_ATTEMPTS = 3
RETRY_SLEEP_SECONDS = 10


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
            print(f"Form page reached — URL: {page.url}")

            payload = make_sample_payload()
            filler = FormFiller(page, payload)

            # ── RETRIEVAL BLOCK WITH RETRY ──────────────────────────────────
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

            # ── WATERMARK BLOCK ─────────────────────────────────────────────
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

            # ── OVERALL VERDICT ──────────────────────────────────────────────
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
