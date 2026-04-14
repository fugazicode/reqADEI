import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from features.submission.portal_session import (
    ADD_TENANT_VERIFICATION_URL,
    PortalSession,
)

KEYWORDS = ("country", "state", "district", "police")
_TRUTHY = {"1", "true", "yes", "y", "on"}


def _is_truthy(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in _TRUTHY

def _matches(entry):
    hay = f"{entry['name']} {entry['id']} {entry['label']}".lower()
    return any(k in hay for k in KEYWORDS)

def _pick_non_india(options):
    for opt in options:
        u = opt.upper()
        if not opt or "SELECT" in u:
            continue
        if "INDIA" in u:
            continue
        return opt
    return None

async def _dump_selects(page, title):
    print(f"\n{title} ({page.url})")
    data = await page.evaluate(
        """() => {
            const selects = Array.from(document.querySelectorAll("select"));
            return selects.map(sel => {
                const name = sel.getAttribute("name") || "";
                const id = sel.id || "";
                const labelEl = sel.id ? document.querySelector('label[for="' + sel.id + '"]') : null;
                const label = labelEl ? labelEl.textContent.trim() : "";
                const options = Array.from(sel.options).map(o => (o.textContent || "").trim());
                return {name, id, label, options};
            });
        }"""
    )
    filtered = [s for s in data if _matches(s)]
    print(json.dumps(filtered, indent=2))
    return filtered

async def _set_select_by_text(page, entry, text):
    await page.evaluate(
        """({name, id, text}) => {
            const sel = name ? document.querySelector('select[name="' + name + '"]') : null
                || (id ? document.getElementById(id) : null);
            if (!sel) return;
            const opt = Array.from(sel.options).find(o => (o.textContent || "").trim() === text);
            if (!opt) return;
            sel.value = opt.value;
            sel.dispatchEvent(new Event("change", {bubbles: true}));
        }""",
        {"name": entry["name"], "id": entry["id"], "text": text},
    )


async def _open_page(pw, *, manual_login: bool, username: str, password: str):
    if not manual_login:
        session = PortalSession(username, password, pw, headless=False)
        page = await session.open()

        async def _close():
            await session.close()

        return page, _close

    browser = await pw.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(ADD_TENANT_VERIFICATION_URL, wait_until="domcontentloaded")
    print("Log in manually and open the Add Tenant Verification form in the browser.")
    input("Press Enter here when the form is visible...")
    if context.pages:
        page = context.pages[-1]

    async def _close():
        await browser.close()

    return page, _close

async def main():
    load_dotenv()
    manual_login = _is_truthy(os.getenv("PORTAL_MANUAL_LOGIN"))
    username = os.getenv("PORTAL_USERNAME", "")
    password = os.getenv("PORTAL_PASSWORD", "")
    if not manual_login and (not username or not password):
        raise SystemExit("Set PORTAL_USERNAME and PORTAL_PASSWORD in your environment or .env")

    async with async_playwright() as pw:
        try:
            page, close_page = await _open_page(
                pw,
                manual_login=manual_login,
                username=username,
                password=password,
            )
        except Exception as exc:
            if manual_login:
                raise
            print(f"Auto login failed: {exc}")
            page, close_page = await _open_page(
                pw,
                manual_login=True,
                username=username,
                password=password,
            )

        # Optional: activate tenant permanent address tab if needed.
        # try:
        #     await page.get_by_text("Tenant Information").click()
        #     await page.get_by_text("Permanent Address").click()
        # except Exception:
        #     pass

        selects = await _dump_selects(page, "Before country change")

        for s in selects:
            if "country" in f"{s['name']} {s['id']} {s['label']}".lower():
                pick = _pick_non_india(s["options"])
                if pick:
                    print(f"Setting {s['name'] or s['id']} to: {pick}")
                    await _set_select_by_text(page, s, pick)

        await page.wait_for_timeout(1500)
        await _dump_selects(page, "After setting non-India")

        await close_page()

if __name__ == "__main__":
    asyncio.run(main())