#!/usr/bin/env python3
"""
scrape_all_stations.py
━━━━━━━━━━━━━━━━━━━━━
Logs into the Delhi Police CCTNS citizen portal and exhaustively scrapes
every state → district → police station combination from the Tenant
Permanent Address dropdowns.

Output
──────
  national_police_stations_full.json   — machine-readable, keyed by state
  national_police_stations_full.csv    — flat CSV for spreadsheet review

Usage
─────
  # Provide credentials via environment variables or .env file
  export PORTAL_USERNAME="your_username"
  export PORTAL_PASSWORD="your_password"

  python scrape_all_stations.py
  python scrape_all_stations.py --headed          # show browser window
  python scrape_all_stations.py --limit 5         # only first 5 states (testing)
  python scrape_all_stations.py --output out/     # custom output directory
  python scrape_all_stations.py --resume          # skip already-scraped states

Requirements
────────────
  pip install playwright python-dotenv
  playwright install chromium
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
LOGGER = logging.getLogger("scraper")

# ── Portal constants ──────────────────────────────────────────────────────────

LOGIN_ENTRY_URL = "https://delhipolice.gov.in/"
CITIZEN_SERVICES_HOME = "https://cctns.delhipolice.gov.in/citizenservices/"
ADD_TENANT_URL = (
    "https://cctns.delhipolice.gov.in/citizenservices/addtenantpgverification.htm"
)

# All 37 Indian states/UTs with their portal select-option values.
# Source: delhi_police_stations.json → states block.
ALL_STATES: dict[str, str] = {
    "ANDAMAN & NICOBAR": "1",
    "ANDHRA PRADESH": "2",
    "ARUNACHAL PRADESH": "3",
    "ASSAM": "4",
    "BIHAR": "5",
    "CHANDIGARH": "6",
    "DAMAN & DIU": "7",
    "DELHI": "8",
    "DADRA & NAGAR HAVELI": "9",
    "GOA": "10",
    "GUJARAT": "11",
    "HIMACHAL PRADESH": "12",
    "HARYANA": "13",
    "JAMMU & KASHMIR": "14",
    "KERALA": "15",
    "KARNATAKA": "16",
    "LAKSHADWEEP": "17",
    "MEGHALAYA": "18",
    "MAHARASHTRA": "19",
    "MANIPUR": "20",
    "MADHYA PRADESH": "21",
    "MIZORAM": "22",
    "NAGALAND": "23",
    "ODISHA": "24",
    "PUNJAB": "25",
    "PUDUCHERRY": "26",
    "RAJASTHAN": "27",
    "SIKKIM": "28",
    "TAMIL NADU": "29",
    "TRIPURA": "30",
    "UTTAR PRADESH": "31",
    "WEST BENGAL": "32",
    "CHHATTISGARH": "33",
    "JHARKHAND": "34",
    "UTTARAKHAND": "35",
    "TELANGANA": "40",
    "LADAKH": "41",
}

# ── Helper: JS-based select (fires jQuery-style change events) ────────────────

async def _js_select_by_value(page, field_name: str, value: str) -> None:
    """Set a <select> by option value and fire the change event."""
    await page.evaluate(
        """([name, val]) => {
            const el = document.querySelector('[name="' + name + '"]');
            if (!el) throw new Error('Element not found: ' + name);
            el.value = val;
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        [field_name, value],
    )


async def _js_select_by_label(page, field_name: str, label: str) -> None:
    """Set a <select> by visible label and fire the change event."""
    await page.evaluate(
        r"""([name, lbl]) => {
            const el = document.querySelector('[name="' + name + '"]');
            if (!el) throw new Error('Element not found: ' + name);
            const clean = s => (s || '').replace(/\s+/g, ' ').trim();
            const opt = Array.from(el.options).find(o => clean(o.textContent) === lbl);
            if (!opt) {
                const avail = Array.from(el.options)
                    .map(o => clean(o.textContent)).join(' | ');
                throw new Error('Label "' + lbl + '" not in ' + name +
                    '. Available: ' + avail);
            }
            el.value = opt.value;
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        [field_name, label],
    )


async def _get_option_labels(page, select_name: str) -> list[str]:
    """Return visible text of all non-placeholder <option> elements."""
    return await page.eval_on_selector_all(
        f'[name="{select_name}"] option',
        r"""els => els
            .map(e => (e.textContent || '').replace(/\s+/g, ' ').trim())
            .filter(t => {
                if (!t) return false;
                const u = t.toUpperCase().replace(/-/g, '').trim();
                return u !== '' && !u.startsWith('SELECT');
            })
        """,
    )


async def _wait_for_select_populated(
    page,
    select_name: str,
    timeout_ms: int = 15_000,
) -> bool:
    """Wait until the select has more than 1 option (i.e. AJAX loaded)."""
    try:
        await page.wait_for_function(
            f"""() => {{
                const s = document.querySelector('[name="{select_name}"]');
                return s && s.options && s.options.length > 1;
            }}""",
            timeout=timeout_ms,
        )
        return True
    except Exception:
        return False


# ── Login & navigate to tenant form ──────────────────────────────────────────

async def _login_and_open_form(pw, *, username: str, password: str, headless: bool):
    """Launch browser, log in, navigate to the Add Tenant Verification form."""
    browser = await pw.chromium.launch(headless=headless, slow_mo=120)
    context = await browser.new_context()
    page = await context.new_page()

    LOGGER.info("Opening portal entry page…")
    await page.goto(LOGIN_ENTRY_URL, wait_until="domcontentloaded", timeout=120_000)

    LOGGER.info("Clicking 'Domestic Help/Tenant Registration' link…")
    await page.wait_for_selector(
        "text=Domestic Help/Tenant Registration", state="visible", timeout=120_000
    )

    async with page.context.expect_page() as new_page_info:
        await page.click("text=Domestic Help/Tenant Registration")
    login_page = await new_page_info.value

    LOGGER.info("Filling credentials…")
    await login_page.wait_for_selector(
        '[name="j_username"]', state="visible", timeout=120_000
    )

    # The portal sets readonly on j_username and removes it via onfocus.
    # Playwright's fill() waits for the element to be editable, so it times out
    # before onfocus fires. Fix: forcibly remove readonly via JS, then fill.
    await login_page.evaluate(
        """() => {
            const u = document.querySelector('[name="j_username"]');
            if (u) { u.removeAttribute('readonly'); u.focus(); }
            const p = document.querySelector('[name="j_password"]');
            if (p) { p.removeAttribute('readonly'); }
        }"""
    )
    await login_page.wait_for_timeout(300)
    await login_page.fill('[name="j_username"]', username)
    await login_page.fill('[name="j_password"]', password)
    await login_page.click("#button")
    await login_page.wait_for_load_state("domcontentloaded", timeout=120_000)

    if "login.htm" in login_page.url:
        await browser.close()
        raise SystemExit(
            "❌ Portal login failed — check PORTAL_USERNAME / PORTAL_PASSWORD."
        )

    LOGGER.info("Login successful. URL: %s", login_page.url)

    LOGGER.info("Navigating to Add Tenant Verification form…")
    await login_page.goto(ADD_TENANT_URL, wait_until="domcontentloaded", timeout=300_000)

    # Wait for ownerFirstName to exist in the DOM (it may be hidden in a TabView panel).
    # Do NOT use state="visible" — the portal hides panels via display:none and
    # Playwright's visibility check fails on this portal's CSS toggle mechanism.
    LOGGER.info("Waiting for form DOM to contain ownerFirstName…")
    await login_page.wait_for_selector(
        '[name="ownerFirstName"]', state="attached", timeout=180_000
    )

    # Explicitly activate the Owner Information tab so its panel becomes visible.
    LOGGER.info("Activating Owner Information tab…")
    await login_page.evaluate(
        r"""() => {
            if (typeof TabView !== 'undefined' && TabView.switchTab) {
                try { TabView.switchTab(0, 0); } catch(e) {}
            }
            const norm = t => (t || '').replace(/\s+/g, ' ').trim();
            for (const a of document.querySelectorAll('a, li, span, div')) {
                if (norm(a.innerText || a.textContent) === 'Owner Information') {
                    a.click();
                    return;
                }
            }
        }"""
    )
    await login_page.wait_for_timeout(1_000)

    # Confirm ownerFirstName is now visible using JS (not Playwright state="visible")
    await login_page.wait_for_function(
        r"""() => {
            const el = document.querySelector('[name="ownerFirstName"]');
            if (!el) return false;
            const st = window.getComputedStyle(el);
            return st.display !== 'none' && st.visibility !== 'hidden' && el.offsetParent !== null;
        }""",
        timeout=60_000,
    )
    LOGGER.info("Form loaded — ownerFirstName is visible.")

    return browser, login_page


# ── Navigate to the Permanent Address sub-tab ─────────────────────────────────

async def _open_permanent_address_tab(page) -> None:
    """
    Navigate to: Tenant Information (top tab) → Address (sub-tab) → Permanent Address (inner tab).

    The portal uses TabView.switchTab(tvIndex, tabIndex) for all navigation.
    Playwright's wait_for_selector with state="visible" fails because the panel
    uses display:none toggling — we check visibility via JS instead.
    """

    # ── Step 1: click Tenant Information top-level tab ────────────────────────
    LOGGER.info("Opening Tenant Information tab…")
    await page.evaluate(
        r"""() => {
            const norm = t => (t || '').replace(/\s+/g, ' ').trim();
            for (const a of document.querySelectorAll('a, li, span, div')) {
                if (norm(a.innerText || a.textContent) === 'Tenant Information') {
                    a.click();
                    return;
                }
            }
        }"""
    )
    # Wait until tenantFirstName is visible (confirms Tenant Personal panel is active)
    await page.wait_for_function(
        r"""() => {
            const el = document.querySelector('[name="tenantFirstName"]');
            if (!el) return false;
            const st = window.getComputedStyle(el);
            return st.display !== 'none' && st.visibility !== 'hidden' && el.offsetParent !== null;
        }""",
        timeout=60_000,
    )
    LOGGER.info("Tenant Information tab active.")

    # ── Step 2: switch to Address sub-tab via TabView.switchTab(1,1) ─────────
    LOGGER.info("Opening Address sub-tab (TabView.switchTab(1,1))…")
    await page.evaluate(
        """() => {
            // Try the direct href link first
            const direct = document.querySelector('[href="javascript:TabView.switchTab(1,1);"]');
            if (direct) { direct.click(); return 'direct'; }
            // Fallback: call TabView API directly if available
            if (typeof TabView !== 'undefined' && TabView.switchTab) {
                TabView.switchTab(1, 1);
                return 'api';
            }
            return 'not_found';
        }"""
    )
    await page.wait_for_timeout(1_000)

    # ── Step 3: switch to Permanent Address inner tab ─────────────────────────
    # Inside the Address panel there is a second TabView (index 2 per CONTEXT.md).
    # "Tenanted Premises Address" = tab 0, "Permanent Address" = tab 1.
    # We try TabView.switchTab(2,1) via JS, then scan all <a href> links as fallback.
    LOGGER.info("Opening Permanent Address inner tab…")
    result = await page.evaluate(
        r"""() => {
            // Try direct TabView API call first
            if (typeof TabView !== 'undefined' && TabView.switchTab) {
                try { TabView.switchTab(2, 1); return 'api_2_1'; } catch(e) {}
                try { TabView.switchTab(2, 2); return 'api_2_2'; } catch(e) {}
            }

            // Scan all TabView switchTab links for one that contains "permanent"
            const norm = s => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
            const want = 'permanent';
            const rx = /TabView\s*\.\s*switchTab\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)/i;

            // Prefer TabView2 links; collect and sort by tab index descending
            const tv2 = [], tvAny = [];
            for (const a of document.querySelectorAll('a[href]')) {
                const href = a.getAttribute('href') || '';
                const m = href.match(rx);
                if (!m) continue;
                const tv = Number(m[1]), tab = Number(m[2]);
                const txt = norm(a.textContent);
                if (txt.includes(want)) {
                    (tv === 2 ? tv2 : tvAny).push({ a, tv, tab });
                }
            }
            const pool = tv2.length ? tv2 : tvAny;
            if (pool.length) {
                // Click the one with the highest tab index (Permanent is after Tenanted)
                pool.sort((x, y) => y.tab - x.tab);
                pool[0].a.click();
                return 'link_tv' + pool[0].tv + '_t' + pool[0].tab;
            }

            // Last resort: click any visible link whose text is "Permanent Address"
            for (const a of document.querySelectorAll('a')) {
                if (norm(a.textContent).includes(want) && a.offsetParent !== null) {
                    a.click();
                    return 'text_fallback';
                }
            }
            return 'not_found';
        }"""
    )
    LOGGER.info("Permanent Address tab click result: %s", result)
    await page.wait_for_timeout(1_000)

    # ── Step 4: confirm tenantPermanentState is now visible via JS ────────────
    # Playwright's visibility check relies on CSS display/visibility/offsetParent.
    # The portal panel may use a non-standard hide mechanism, so we poll with JS.
    LOGGER.info("Waiting for tenantPermanentState to become visible…")
    try:
        await page.wait_for_function(
            r"""() => {
                const el = document.querySelector('[name="tenantPermanentState"]');
                if (!el) return false;
                const st = window.getComputedStyle(el);
                return st.display !== 'none' && st.visibility !== 'hidden' && el.offsetParent !== null;
            }""",
            timeout=60_000,
        )
        LOGGER.info("Permanent Address tab ready (tenantPermanentState visible).")
    except Exception:
        # If still hidden, try one more TabView permutation then continue anyway
        LOGGER.warning(
            "tenantPermanentState still hidden after %s — trying TabView(2,2) brute force", result
        )
        await page.evaluate(
            """() => {
                for (let t = 0; t <= 5; t++) {
                    try {
                        if (typeof TabView !== 'undefined') TabView.switchTab(2, t);
                    } catch(e) {}
                    const el = document.querySelector('[name="tenantPermanentState"]');
                    if (el && el.offsetParent !== null) return t;
                }
                return -1;
            }"""
        )
        await page.wait_for_timeout(1_000)
        LOGGER.info("Brute-force TabView sweep done — proceeding.")


# ── Core scrape loop ──────────────────────────────────────────────────────────

async def _scrape_state(
    page,
    state_name: str,
    state_value: str,
    *,
    district_timeout_ms: int = 20_000,
    station_timeout_ms: int = 15_000,
) -> dict[str, list[str]]:
    """
    Select a state, then iterate every district to collect police stations.
    Returns { DISTRICT_NAME: [station, ...] }
    """
    result: dict[str, list[str]] = {}

    # ── Select state ──────────────────────────────────────────────────────────
    try:
        async with page.expect_response(
            lambda r: "getdistricts" in r.url.lower(),
            timeout=district_timeout_ms,
        ):
            await _js_select_by_value(page, "tenantPermanentState", state_value)

        populated = await _wait_for_select_populated(
            page, "tenantPermanentDistrict", timeout_ms=district_timeout_ms
        )
        if not populated:
            LOGGER.warning("  Districts did not populate for %s — skipping", state_name)
            return result

    except Exception as exc:
        LOGGER.warning(
            "  District load failed for %s: %s — skipping", state_name, exc
        )
        return result

    district_labels = await _get_option_labels(page, "tenantPermanentDistrict")
    LOGGER.info("  Found %d districts", len(district_labels))

    # ── Iterate districts ─────────────────────────────────────────────────────
    for d_label in district_labels:
        if not d_label:
            continue
        d_key = d_label.strip().upper()

        try:
            async with page.expect_response(
                lambda r: "getpolicestations" in r.url.lower(),
                timeout=station_timeout_ms,
            ):
                await _js_select_by_label(page, "tenantPermanentDistrict", d_label)

            populated = await _wait_for_select_populated(
                page, "tenantPermanentPoliceStation", timeout_ms=station_timeout_ms
            )
            if not populated:
                LOGGER.debug("    No stations for district %s", d_key)
                result[d_key] = []
                continue

        except Exception as exc:
            LOGGER.debug("    Station load failed for %s / %s: %s", state_name, d_label, exc)
            # Still record the district with empty station list
            result[d_key] = []
            continue

        stations = await _get_option_labels(page, "tenantPermanentPoliceStation")
        result[d_key] = [s.strip() for s in stations if s.strip()]
        LOGGER.debug(
            "    %s → %d stations", d_key, len(result[d_key])
        )

    return result


# ── Retry wrapper ─────────────────────────────────────────────────────────────

async def _scrape_state_with_retry(
    page,
    state_name: str,
    state_value: str,
    max_retries: int = 2,
) -> dict[str, list[str]]:
    for attempt in range(1, max_retries + 1):
        try:
            result = await _scrape_state(page, state_name, state_value)
            return result
        except Exception as exc:
            LOGGER.warning(
                "  Attempt %d/%d failed for %s: %s",
                attempt, max_retries, state_name, exc,
            )
            if attempt < max_retries:
                await page.wait_for_timeout(2000)
    return {}


# ── Output writers ────────────────────────────────────────────────────────────

def _write_json(
    by_state: dict[str, dict[str, list[str]]],
    output_dir: Path,
    states_scraped: int,
) -> Path:
    payload = {
        "_meta": {
            "source": "scrape_all_stations.py",
            "scraped_at": datetime.utcnow().isoformat() + "Z",
            "states_scraped": states_scraped,
            "total_states": len(ALL_STATES),
            "description": (
                "Nested map: state_name → district_name → [police_station_name, ...]"
            ),
        },
        "by_state": by_state,
    }
    out = output_dir / "national_police_stations_full.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info("JSON written → %s", out)
    return out


def _write_csv(
    by_state: dict[str, dict[str, list[str]]],
    output_dir: Path,
) -> Path:
    out = output_dir / "national_police_stations_full.csv"
    rows: list[dict] = []
    for state, districts in sorted(by_state.items()):
        for district, stations in sorted(districts.items()):
            if stations:
                for station in stations:
                    rows.append(
                        {"state": state, "district": district, "police_station": station}
                    )
            else:
                rows.append({"state": state, "district": district, "police_station": ""})

    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["state", "district", "police_station"])
        writer.writeheader()
        writer.writerows(rows)

    LOGGER.info("CSV  written → %s  (%d rows)", out, len(rows))
    return out


def _write_progress_snapshot(
    by_state: dict[str, dict[str, list[str]]],
    output_dir: Path,
) -> None:
    """Overwrite a progress file after each state so scraping can be resumed."""
    snap = output_dir / "_progress_snapshot.json"
    snap.write_text(json.dumps(by_state, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_progress_snapshot(output_dir: Path) -> dict[str, dict[str, list[str]]]:
    snap = output_dir / "_progress_snapshot.json"
    if snap.exists():
        LOGGER.info("Resuming from snapshot: %s", snap)
        return json.loads(snap.read_text(encoding="utf-8"))
    return {}


# ── Summary printer ───────────────────────────────────────────────────────────

def _print_summary(by_state: dict[str, dict[str, list[str]]]) -> None:
    total_districts = sum(len(d) for d in by_state.values())
    total_stations = sum(
        len(s) for d in by_state.values() for s in d.values()
    )
    print("\n" + "═" * 60)
    print(f"  States scraped  : {len(by_state):>5}")
    print(f"  Total districts : {total_districts:>5}")
    print(f"  Total stations  : {total_stations:>5}")
    print("═" * 60)
    print(f"  {'STATE':<35}  DISTRICTS  STATIONS")
    print("  " + "-" * 55)
    for state, districts in sorted(by_state.items()):
        n_d = len(districts)
        n_s = sum(len(v) for v in districts.values())
        print(f"  {state:<35}  {n_d:>9}  {n_s:>8}")
    print("═" * 60 + "\n")


# ── Main entry point ──────────────────────────────────────────────────────────

async def _async_main(
    username: str,
    password: str,
    *,
    headed: bool,
    limit: Optional[int],
    output_dir: Path,
    resume: bool,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    by_state: dict[str, dict[str, list[str]]] = {}
    if resume:
        by_state = _load_progress_snapshot(output_dir)
        already_done = set(by_state.keys())
        LOGGER.info("Resuming — %d states already scraped", len(already_done))
    else:
        already_done: set[str] = set()

    state_items = sorted(ALL_STATES.items(), key=lambda x: x[0])
    if limit is not None:
        state_items = state_items[:limit]

    # Filter out already-scraped states when resuming
    pending = [
        (name, val) for name, val in state_items if name not in already_done
    ]
    LOGGER.info(
        "States to scrape: %d  (total target: %d)", len(pending), len(state_items)
    )

    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser, page = await _login_and_open_form(
            pw, username=username, password=password, headless=not headed
        )
        try:
            await _open_permanent_address_tab(page)

            for idx, (state_name, state_value) in enumerate(pending, start=1):
                LOGGER.info(
                    "[%d/%d] Scraping: %s (portal value=%s)",
                    idx, len(pending), state_name, state_value,
                )
                t0 = time.perf_counter()
                districts = await _scrape_state_with_retry(
                    page, state_name, state_value
                )
                elapsed = time.perf_counter() - t0
                n_d = len(districts)
                n_s = sum(len(v) for v in districts.values())
                LOGGER.info(
                    "  ✓ %s — %d districts, %d stations (%.1fs)",
                    state_name, n_d, n_s, elapsed,
                )
                by_state[state_name] = districts
                # Save progress after every state
                _write_progress_snapshot(by_state, output_dir)

        finally:
            await browser.close()

    # Write final outputs
    _write_json(by_state, output_dir, states_scraped=len(by_state))
    _write_csv(by_state, output_dir)
    _print_summary(by_state)


def main() -> None:
    # Try loading .env if python-dotenv is available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(
        description="Scrape all state/district/police-station data from the Delhi Police portal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--username",
        default=os.getenv("PORTAL_USERNAME", ""),
        help="Portal login username (default: $PORTAL_USERNAME)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("PORTAL_PASSWORD", ""),
        help="Portal login password (default: $PORTAL_PASSWORD)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser window (default: headless)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Only scrape the first N states (useful for testing)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scraped_data"),
        metavar="DIR",
        help="Directory for output files (default: ./scraped_data)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from a previous partial scrape (reads _progress_snapshot.json)",
    )
    args = parser.parse_args()

    if not args.username or not args.password:
        parser.error(
            "Portal credentials required.\n"
            "Set PORTAL_USERNAME and PORTAL_PASSWORD environment variables,\n"
            "or pass --username / --password flags."
        )

    asyncio.run(
        _async_main(
            args.username,
            args.password,
            headed=args.headed,
            limit=args.limit,
            output_dir=args.output.resolve(),
            resume=args.resume,
        )
    )


if __name__ == "__main__":
    main()
