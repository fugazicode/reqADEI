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
    from features.submission.form_filler import FormFiller
    from tests.sample_payload import make_sample_payload
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    print("Ensure portal_session.py and form_filler.py are implemented before running this test.")
    raise SystemExit(1)


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

            print("Filling owner tab first (required before tenant tab)...")
            await filler._fill_owner_tab()

            print("Filling tenant personal information tab...")
            await filler._fill_tenant_personal_tab()

            first_name = await page.locator('[name="tenantFirstName"]').input_value()
            relation_type = await page.locator('[name="tenantRelationType"]').input_value()
            purpose = await page.locator('[name="tenancypurpose"]').input_value()

            print(f"tenantFirstName    = '{first_name}'")
            print(f"tenantRelationType = '{relation_type}'")
            print(f"tenancypurpose     = '{purpose}'")

            if first_name and relation_type and purpose:
                print("TENANT PERSONAL OK — all three verification fields populated")
            else:
                print("WARNING — one or more fields are empty after fill")
                print("Inspect the browser to see which field was not filled.")

            if purpose != "Residential":
                print("WARNING — tenancypurpose should be 'Residential'")
        except Exception:
            print("FAILED")
            traceback.print_exc()
        finally:
            print("Press Enter to close browser...")
            input()
            await session.close()


asyncio.run(main())
