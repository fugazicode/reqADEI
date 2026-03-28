import asyncio
import os
import pathlib
import sys
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from aiogram import Bot
from aiogram.types import BufferedInputFile
from playwright.async_api import async_playwright

try:
    from features.submission.portal_session import PortalSession
    from features.submission.form_filler import FormFiller
    from tests.sample_payload import make_sample_payload
    from utils.watermark import apply_watermark
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    raise SystemExit(1)

# ── TEST CONSTANT ────────────────────────────────────────────────────────────
# Hardcoded for isolated testing. When moving to full flow testing, replace
# this with: REQUEST_NUMBER = await filler.fill(IMAGE_BYTES)
REQUEST_NUMBER = "816726116865"
# ────────────────────────────────────────────────────────────────────────────


async def main() -> None:
    load_dotenv()

    portal_username = os.getenv("PORTAL_USERNAME", "")
    portal_password = os.getenv("PORTAL_PASSWORD", "")
    bot_token = os.getenv("BOT_TOKEN", "")
    admin_telegram_id = os.getenv("ADMIN_TELEGRAM_ID", "")

    if not all([portal_username, portal_password, bot_token, admin_telegram_id]):
        print("ERROR: PORTAL_USERNAME, PORTAL_PASSWORD, BOT_TOKEN, and ADMIN_TELEGRAM_ID must be set in .env")
        return

    recipient_id = int(admin_telegram_id)
    bot = Bot(token=bot_token)

    async with async_playwright() as pw:
        session = PortalSession(portal_username, portal_password, pw)
        try:
            # ── STEP 1: Login ────────────────────────────────────────────────
            print("Step 1: Logging in to portal...")
            page = await session.open()
            print(f"  PASS — form page reached: {page.url}")

            payload = make_sample_payload()
            filler = FormFiller(page, payload)

            # ── STEP 2: Retrieve PDF ─────────────────────────────────────────
            print(f"\nStep 2: Retrieving PDF for request_number={REQUEST_NUMBER}...")
            pdf_bytes = await filler._retrieve_pdf(REQUEST_NUMBER)
            if len(pdf_bytes) > 1000 and pdf_bytes[:4] == b"%PDF":
                print(f"  PASS — retrieved {len(pdf_bytes)} bytes")
            else:
                print(f"  FAIL — unexpected content ({len(pdf_bytes)} bytes, magic={pdf_bytes[:4]})")
                return

            # ── STEP 3: Watermark ────────────────────────────────────────────
            print("\nStep 3: Applying watermark...")
            try:
                watermarked_bytes = apply_watermark(pdf_bytes)
                if watermarked_bytes[:4] == b"%PDF" and len(watermarked_bytes) > len(pdf_bytes):
                    print(f"  PASS — watermarked PDF is {len(watermarked_bytes)} bytes")
                else:
                    print(f"  FAIL — watermark did not produce larger PDF")
                    print(f"  original={len(pdf_bytes)} watermarked={len(watermarked_bytes)}")
                    return
            except Exception:
                print("  FAIL — exception during watermarking")
                traceback.print_exc()
                return

            # ── STEP 4: Send to Telegram ─────────────────────────────────────
            print(f"\nStep 4: Sending watermarked PDF to Telegram user {recipient_id}...")
            try:
                await bot.send_document(
                    chat_id=recipient_id,
                    document=BufferedInputFile(watermarked_bytes, "preview.pdf"),
                    caption="Preview of your verification document.",
                )
                print("  PASS — document sent successfully")
            except Exception:
                print("  FAIL — exception during Telegram send")
                traceback.print_exc()
                return

            print("\nOVERALL — PASS")

        except Exception:
            print("\nEXCEPTION during test")
            traceback.print_exc()
        finally:
            await session.close()
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
