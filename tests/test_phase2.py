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
            print("Form page reached. Filling owner tab...")

            payload = make_sample_payload()
            filler = FormFiller(page, payload)

            await filler._fill_owner_tab()
            print("Owner tab fill completed.")

            hidden_district = await page.input_value('[name="hiddenownerDistrict"]')
            hidden_station = await page.input_value('[name="hiddenownerPStation"]')
            print(f"hiddenownerDistrict = '{hidden_district}'")
            print(f"hiddenownerPStation  = '{hidden_station}'")

            if hidden_district and hidden_station:
                print("HIDDEN FIELDS OK — JavaScript sync confirmed working")
            else:
                print("WARNING — one or both hidden fields are empty")
                print("This means the district/station JavaScript sync did not fire.")
                print("Check _select_district_and_station in form_filler.py.")
        except Exception:
            print("FAILED")
            traceback.print_exc()
        finally:
            print("Press Enter to close browser...")
            input()
            await session.close()


asyncio.run(main())
