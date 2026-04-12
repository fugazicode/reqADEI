#!/usr/bin/env python3
"""
Convert a flat state/district/police_station CSV into data/national_police_stations.json.

Usage (from repo root):
    python scripts/import_stations_csv.py --input path/to/your_file.csv
    python scripts/import_stations_csv.py --input path/to/your_file.csv --output data/national_police_stations.json
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
from collections import defaultdict
from pathlib import Path

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "data" / "national_police_stations.json"

# Canonical state keys exactly as they appear in form_filler.STATE_VALUES.
# Keep in sync: when the portal adds a state, update STATE_VALUES and this set.
# Intentional duplicate of dict keys (no runtime import of form_filler) — run
# sync-check: _KNOWN_STATES == frozenset(form_filler.STATE_VALUES.keys()).
_KNOWN_STATES: frozenset[str] = frozenset(
    {
        "ANDAMAN & NICOBAR",
        "ANDHRA PRADESH",
        "ARUNACHAL PRADESH",
        "ASSAM",
        "BIHAR",
        "CHANDIGARH",
        "CHHATTISGARH",
        "DADRA & NAGAR HAVELI",
        "DAMAN & DIU",
        "DELHI",
        "GOA",
        "GUJARAT",
        "HARYANA",
        "HIMACHAL PRADESH",
        "JAMMU & KASHMIR",
        "JHARKHAND",
        "KARNATAKA",
        "KERALA",
        "LADAKH",
        "LAKSHADWEEP",
        "MADHYA PRADESH",
        "MAHARASHTRA",
        "MANIPUR",
        "MEGHALAYA",
        "MIZORAM",
        "NAGALAND",
        "ODISHA",
        "PUDUCHERRY",
        "PUNJAB",
        "RAJASTHAN",
        "SIKKIM",
        "TAMIL NADU",
        "TELANGANA",
        "TRIPURA",
        "UTTAR PRADESH",
        "UTTARAKHAND",
        "WEST BENGAL",
    }
)


def _validate_states(
    by_state: dict[str, dict[str, list[str]]],
) -> tuple[list[str], list[str]]:
    """
    Compare CSV state names against _KNOWN_STATES.

    Returns:
        matched   — state names that are recognised
        unmatched — state names that will be silently ignored by the form filler
    """
    matched = []
    unmatched = []
    for state in sorted(by_state.keys()):
        if state in _KNOWN_STATES:
            matched.append(state)
        else:
            unmatched.append(state)
    return matched, unmatched


def _per_state_summary(
    by_state: dict[str, dict[str, list[str]]],
) -> None:
    """Log district count and total station count per state for quick sanity check."""
    for state in sorted(by_state.keys()):
        districts = by_state[state]
        total_stations = sum(len(v) for v in districts.values())
        LOGGER.info(
            "  %-35s  %3d districts  %5d stations",
            state,
            len(districts),
            total_stations,
        )


def convert(input_path: Path, output_path: Path, *, abort_on_unknown: bool) -> None:
    by_state: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    seen: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    row_count = 0
    skip_count = 0

    with input_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)

        expected = {"state", "district", "police_station"}
        if not expected.issubset(set(reader.fieldnames or [])):
            raise SystemExit(
                f"CSV is missing required columns. "
                f"Found: {reader.fieldnames}. Expected: {sorted(expected)}"
            )

        for lineno, row in enumerate(reader, start=2):
            state = (row["state"] or "").strip()
            district = (row["district"] or "").strip()
            station = (row["police_station"] or "").strip()

            if not state or not district or not station:
                LOGGER.warning(
                    "Line %d: skipping incomplete row: %r", lineno, row
                )
                skip_count += 1
                continue

            if station not in seen[state][district]:
                by_state[state][district].append(station)
                seen[state][district].add(station)

            row_count += 1

    # --- State name validation ---
    matched, unmatched = _validate_states(by_state)

    LOGGER.info("State validation - %d matched, %d unmatched", len(matched), len(unmatched))

    if unmatched:
        LOGGER.warning(
            "The following %d state name(s) from the CSV do not match any key in "
            "STATE_VALUES and will be silently ignored by the form filler at submission time:",
            len(unmatched),
        )
        for name in unmatched:
            district_count = len(by_state[name])
            station_count = sum(len(v) for v in by_state[name].values())
            LOGGER.warning(
                "  UNMATCHED: %r  (%d districts, %d stations affected)",
                name,
                district_count,
                station_count,
            )
        if abort_on_unknown:
            raise SystemExit(
                "Aborting because --abort-on-unknown is set and unmatched states were found. "
                "Fix the state names in the CSV or add them to _KNOWN_STATES, then re-run."
            )
        LOGGER.warning(
            "Continuing anyway (pass --abort-on-unknown to treat this as a hard error)."
        )

    # --- Per-state summary ---
    LOGGER.info("Per-state summary:")
    _per_state_summary(by_state)

    # --- Write output ---
    plain: dict[str, dict[str, list[str]]] = {
        state: dict(districts)
        for state, districts in sorted(by_state.items())
    }

    payload = {
        "_meta": {
            "source": f"scripts/import_stations_csv.py --input {input_path.name}",
            "states_scraped": len(plain),
            "states_unmatched": unmatched,
        },
        "by_state": plain,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    LOGGER.info(
        "Done. %d rows imported, %d skipped. %d states written to %s",
        row_count,
        skip_count,
        len(plain),
        output_path,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the source CSV file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the JSON (default: data/national_police_stations.json)",
    )
    parser.add_argument(
        "--abort-on-unknown",
        action="store_true",
        help="Exit with an error if any state name is not in STATE_VALUES, instead of warning and continuing",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        raise SystemExit(f"Input file not found: {args.input}")

    convert(
        args.input.resolve(),
        args.output.resolve(),
        abort_on_unknown=args.abort_on_unknown,
    )


if __name__ == "__main__":
    main()
