#!/usr/bin/env python3
"""
Convert docs/list.csv → data/national_police_stations.json

The output schema matches what `StationLookup` (`utils/station_lookup.py`) expects:
  {
    "_meta": { ... },
    "by_state": {
      "UTTAR PRADESH": {
        "AGRA": ["CENTRAL PS", "CIVIL LINES", ...],
        ...
      },
      ...
    }
  }

Usage (from repo root):
    python scripts/build_national_stations_json.py
    python scripts/build_national_stations_json.py --csv docs/list.csv --output data/national_police_stations.json

`_KNOWN_STATE_KEYS` must stay aligned with `STATE_VALUES` keys in
`features/submission/form_filler.py` (portal state dropdown).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = REPO_ROOT / "docs" / "list.csv"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "national_police_stations.json"

# Canonical state spellings from form_filler.STATE_VALUES.
# Used only for validation warnings — the script still writes states
# that don't match, because the portal may serve states not in this set.
_KNOWN_STATE_KEYS: frozenset[str] = frozenset({
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
})


def _normalize(value: str) -> str:
    # Mirrors StationLookup._normalize so runtime matching and build-time
    # validation use identical logic — lowercase, strip, collapse whitespace,
    # replace hyphens with spaces.
    return value.strip().lower().replace("-", " ")


def _is_delhi(state: str) -> bool:
    # StationLookup already routes Delhi to delhi_police_stations.json via
    # _is_delhi_state(); skip these rows so the national file doesn't shadow
    # the Delhi-specific data.
    return _normalize(state) in (
        "delhi",
        "nct of delhi",
        "national capital territory of delhi",
    )


def build(csv_path: Path, output_path: Path) -> None:
    if not csv_path.is_file():
        LOGGER.error("CSV not found: %s", csv_path)
        sys.exit(1)

    # by_state[STATE][DISTRICT] = ordered set of station names (built as list,
    # deduplication applied at the end). Using defaultdict avoids key-existence
    # checks in the hot loop.
    by_state: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    # Track which (state, district) pairs have already had a given station added
    # so duplicates in the CSV are silently dropped.
    seen: dict[tuple[str, str], set[str]] = defaultdict(set)

    rows_read = 0
    rows_skipped_delhi = 0
    rows_skipped_bad = 0

    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)

        # Validate header matches the expected schema described in the brief.
        expected = {"state", "district", "police_station"}
        if reader.fieldnames is None or not expected.issubset(set(reader.fieldnames)):
            LOGGER.error(
                "CSV header mismatch. Expected columns %s, got: %s",
                expected,
                reader.fieldnames,
            )
            sys.exit(1)

        for row in reader:
            rows_read += 1

            state = (row.get("state") or "").strip()
            district = (row.get("district") or "").strip()
            station = (row.get("police_station") or "").strip()

            # Blank fields indicate a malformed row; skip and count.
            if not state or not district or not station:
                rows_skipped_bad += 1
                LOGGER.debug("Skipping incomplete row %d: %r", rows_read, row)
                continue

            if _is_delhi(state):
                rows_skipped_delhi += 1
                continue

            key = (state, district)
            if station not in seen[key]:
                seen[key].add(station)
                by_state[state][district].append(station)

    # Sort station lists so the output is deterministic and diff-friendly.
    sorted_by_state: dict[str, dict[str, list[str]]] = {
        state: {
            district: sorted(stations)
            for district, stations in sorted(districts.items())
        }
        for state, districts in sorted(by_state.items())
    }

    # Validation pass: warn for any state name that won't resolve against
    # STATE_VALUES at runtime. This never blocks the write — just surfaces
    # mismatches early so they can be corrected in the source CSV or the
    # _KNOWN_STATE_KEYS set above.
    unmatched_states: list[str] = []
    for state in sorted_by_state:
        if state not in _KNOWN_STATE_KEYS:
            # Try the same normalize comparison StationLookup uses at runtime.
            norm_state = _normalize(state)
            matched = any(
                _normalize(known) == norm_state for known in _KNOWN_STATE_KEYS
            )
            if not matched:
                unmatched_states.append(state)

    if unmatched_states:
        LOGGER.warning(
            "These %d state name(s) from the CSV have no match in STATE_VALUES "
            "and may not resolve at runtime: %s",
            len(unmatched_states),
            unmatched_states,
        )

    total_districts = sum(len(d) for d in sorted_by_state.values())
    total_stations = sum(
        len(s) for d in sorted_by_state.values() for s in d.values()
    )

    payload = {
        "_meta": {
            "source": str(csv_path.relative_to(REPO_ROOT)),
            "states": len(sorted_by_state),
            "districts": total_districts,
            "stations": total_stations,
        },
        "by_state": sorted_by_state,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    LOGGER.info(
        "Wrote %s — %d states, %d districts, %d stations "
        "(%d Delhi rows skipped, %d bad rows skipped, %d unmatched state names)",
        output_path,
        len(sorted_by_state),
        total_districts,
        total_stations,
        rows_skipped_delhi,
        rows_skipped_bad,
        len(unmatched_states),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="Source CSV (default: docs/list.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON path (default: data/national_police_stations.json)",
    )
    args = parser.parse_args()
    build(args.csv.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
