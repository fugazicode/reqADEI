"""Load a persisted submission snapshot and run Playwright fill + PDF retrieval (no bot).

Usage (from repo root):

    python -m scripts.run_submission_snapshot
    python -m scripts.run_submission_snapshot --snapshot data/submission_snapshot --output out.pdf

Requires ``PORTAL_USERNAME`` and ``PORTAL_PASSWORD`` in the environment (e.g. ``.env``).

Populate ``data/submission_snapshot`` by running the bot with ``SUBMISSION_SNAPSHOT_DIR`` set,
or copy ``manifest.json`` + ``tenant_image.bin`` from another machine.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from features.submission.submission_worker import execute_playwright_submission
from infrastructure.submission_snapshot import load_snapshot


def _require_portal_creds() -> tuple[str, str]:
    user = os.getenv("PORTAL_USERNAME", "").strip()
    password = os.getenv("PORTAL_PASSWORD", "").strip()
    if not user or not password:
        raise SystemExit(
            "Set PORTAL_USERNAME and PORTAL_PASSWORD (e.g. in .env) before running this script."
        )
    return user, password


async def _async_main(snapshot_dir: Path, output_pdf: Path, headless: bool) -> None:
    inp = load_snapshot(snapshot_dir)
    user, password = _require_portal_creds()
    async with async_playwright() as pw:
        request_number, pdf_bytes = await execute_playwright_submission(
            inp,
            pw,
            portal_username=user,
            portal_password=password,
            headless=headless,
        )
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_pdf.write_bytes(pdf_bytes)
    print(f"request_number={request_number!r} wrote {output_pdf} ({len(pdf_bytes)} bytes)")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path("data/submission_snapshot"),
        help="Directory containing manifest.json and tenant_image.bin",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/submission_snapshot/out/verification.pdf"),
        help="Where to write the downloaded PDF",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser headless (default: visible window)",
    )
    args = parser.parse_args()
    asyncio.run(_async_main(args.snapshot.resolve(), args.output.resolve(), args.headless))


if __name__ == "__main__":
    main()
