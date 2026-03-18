# Run order: test_phase1 → test_phase2 → test_phase3_tenant → test_phase4_addresses → test_full_fill
# Do not skip ahead. Each phase depends on the previous one passing.

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

            print("Running prerequisite fills...")
            await filler._fill_owner_tab()
            await filler._fill_tenant_personal_tab()
            await filler._navigate_to_address_subtab()
            print("Prerequisites complete. Filling tenanted premises address...")

            await filler._fill_tenant_address_tenanted()

            hidden_pres_d = await page.input_value('[name="hidtenantPrestDistrict"]')
            hidden_pres_s = await page.input_value('[name="hidtenantPresPStation"]')
            print(f"Tenanted premises — hidtenantPrestDistrict = '{hidden_pres_d}'")
            print(f"Tenanted premises — hidtenantPresPStation  = '{hidden_pres_s}'")

            if hidden_pres_d and hidden_pres_s:
                print("TENANTED ADDRESS HIDDEN FIELDS OK")
            else:
                print("WARNING — tenanted address hidden fields empty")

            await filler._fill_tenant_address_permanent()

            hidden_perm_d = await page.input_value('[name="hidtenantPermtDistrict"]')
            hidden_perm_s = await page.input_value('[name="hidtenantPermPStation"]')
            print(f"Permanent address — hidtenantPermtDistrict = '{hidden_perm_d}'")
            print(f"Permanent address — hidtenantPermPStation  = '{hidden_perm_s}'")

            payload = make_sample_payload()
            permanent_district = payload.tenant.address.district if payload.tenant.address else None

            if permanent_district is None:
                print("Permanent address district is None — hidden fields expected to be empty for non-Delhi address")
                print("PERMANENT ADDRESS OK — non-Delhi state handled correctly")
            else:
                if hidden_perm_d and hidden_perm_s:
                    print("PERMANENT ADDRESS HIDDEN FIELDS OK")
                else:
                    print("WARNING — permanent address hidden fields empty but district was provided")
                    print("Check _select_district_and_station for permanent address context.")
        except Exception:
            print("FAILED")
            traceback.print_exc()
        finally:
            print("Press Enter to close browser...")
            input()
            await session.close()


asyncio.run(main())
