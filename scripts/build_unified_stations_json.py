#!/usr/bin/env python3
"""
Build a unified police station dataset from:
  - data/delhi_police_stations.json
  - data/national_police_stations.json

Output schema:
  {
    "_meta": { ... },
    "states": { "STATE": "portal_state_id", ... },
    "by_state": {
      "STATE": {
        "DISTRICT": {
          "district_id": "..." | null,
          "stations": {
            "STATION": "..." | null
          }
        }
      }
    }
  }

Notes:
  - Delhi data remains source-of-truth for district/station IDs.
  - National rows are merged as label catalog entries unless IDs exist.
  - Use --require-full-ids to fail when any district/station ID is null.

Usage:
  python scripts/build_unified_stations_json.py
  python scripts/build_unified_stations_json.py --require-full-ids
  python scripts/build_unified_stations_json.py --validate-only
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DELHI = REPO_ROOT / "data" / "delhi_police_stations.json"
DEFAULT_NATIONAL = REPO_ROOT / "data" / "national_police_stations.json"
DEFAULT_OUTPUT = REPO_ROOT / "data" / "police_stations.json"

DELHI_ALIASES: tuple[str, ...] = (
    "delhi",
    "nct of delhi",
    "national capital territory of delhi",
)


def _normalize(value: str) -> str:
    return value.strip().lower().replace("-", " ")


def _is_delhi(value: str) -> bool:
    return _normalize(value) in DELHI_ALIASES


def _load_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _as_clean_str(value: object) -> str:
    return str(value).strip()


def _clean_station_names(values: Iterable[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        name = _as_clean_str(raw)
        if not name:
            continue
        if "SELECT" in name.upper():
            continue
        key = name.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return sorted(out)


def _merge_delhi(delhi: dict, by_state: dict[str, dict]) -> None:
    districts_raw = delhi.get("districts", {})
    stations_raw = delhi.get("stations", {})

    delhi_block: dict[str, dict] = {}

    if isinstance(districts_raw, dict):
        for district_name, district_id in districts_raw.items():
            d_name = _as_clean_str(district_name).upper()
            d_id = _as_clean_str(district_id) if district_id is not None else None
            station_map_raw = stations_raw.get(district_name, {}) if isinstance(stations_raw, dict) else {}
            station_map: dict[str, str | None] = {}
            if isinstance(station_map_raw, dict):
                for station_name, station_id in station_map_raw.items():
                    s_name = _as_clean_str(station_name)
                    if not s_name or "SELECT" in s_name.upper():
                        continue
                    station_map[s_name] = _as_clean_str(station_id) if station_id is not None else None
            delhi_block[d_name] = {
                "district_id": d_id,
                "stations": dict(sorted(station_map.items())),
            }

    # Include districts that exist only under stations map but not in districts table.
    if isinstance(stations_raw, dict):
        for district_name, station_map_raw in stations_raw.items():
            d_name = _as_clean_str(district_name).upper()
            if d_name in delhi_block:
                continue
            station_map: dict[str, str | None] = {}
            if isinstance(station_map_raw, dict):
                for station_name, station_id in station_map_raw.items():
                    s_name = _as_clean_str(station_name)
                    if not s_name or "SELECT" in s_name.upper():
                        continue
                    station_map[s_name] = _as_clean_str(station_id) if station_id is not None else None
            delhi_block[d_name] = {
                "district_id": None,
                "stations": dict(sorted(station_map.items())),
            }

    by_state["DELHI"] = dict(sorted(delhi_block.items()))


def _merge_national(national: dict, by_state: dict[str, dict]) -> None:
    root = national.get("by_state", national)
    if not isinstance(root, dict):
        return

    for state_name, districts_raw in root.items():
        s_name = _as_clean_str(state_name).upper()
        if not s_name or s_name.startswith("_"):
            continue
        if _is_delhi(s_name):
            # Keep Delhi from Delhi file as source-of-truth.
            continue
        if not isinstance(districts_raw, dict):
            continue

        state_block = by_state.setdefault(s_name, {})

        for district_name, stations_raw in districts_raw.items():
            d_name = _as_clean_str(district_name).upper()
            if not d_name or "SELECT" in d_name:
                continue

            entry = state_block.setdefault(
                d_name,
                {
                    "district_id": None,
                    "stations": {},
                },
            )

            station_map = entry.get("stations", {})
            if not isinstance(station_map, dict):
                station_map = {}

            if isinstance(stations_raw, list):
                for station_name in _clean_station_names(stations_raw):
                    station_map.setdefault(station_name, None)
            elif isinstance(stations_raw, dict):
                for station_name, station_id in stations_raw.items():
                    s_name_clean = _as_clean_str(station_name)
                    if not s_name_clean or "SELECT" in s_name_clean.upper():
                        continue
                    cleaned_id = _as_clean_str(station_id) if station_id is not None else None
                    # Preserve any non-null ID over null.
                    if s_name_clean not in station_map or station_map[s_name_clean] is None:
                        station_map[s_name_clean] = cleaned_id

            entry["stations"] = dict(sorted(station_map.items()))

        by_state[s_name] = dict(sorted(state_block.items()))


def _compute_stats(by_state: dict[str, dict]) -> dict[str, int]:
    total_states = len(by_state)
    total_districts = 0
    total_stations = 0
    districts_with_ids = 0
    stations_with_ids = 0

    for districts in by_state.values():
        if not isinstance(districts, dict):
            continue
        total_districts += len(districts)
        for district_entry in districts.values():
            if not isinstance(district_entry, dict):
                continue
            if district_entry.get("district_id") is not None:
                districts_with_ids += 1
            stations = district_entry.get("stations", {})
            if not isinstance(stations, dict):
                continue
            total_stations += len(stations)
            for station_id in stations.values():
                if station_id is not None:
                    stations_with_ids += 1

    return {
        "states": total_states,
        "districts": total_districts,
        "stations": total_stations,
        "districts_with_ids": districts_with_ids,
        "stations_with_ids": stations_with_ids,
    }


def _validate_required_ids(payload: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    by_state = payload.get("by_state", {})
    if not isinstance(by_state, dict):
        return False, ["Payload missing object key: by_state"]

    for state_name, districts in by_state.items():
        if not isinstance(districts, dict):
            errors.append(f"State '{state_name}' districts block is not an object")
            continue
        for district_name, district_entry in districts.items():
            if not isinstance(district_entry, dict):
                errors.append(
                    f"District '{state_name}/{district_name}' entry is not an object"
                )
                continue
            if district_entry.get("district_id") is None:
                errors.append(f"Missing district_id for '{state_name}/{district_name}'")
            stations = district_entry.get("stations", {})
            if not isinstance(stations, dict):
                errors.append(
                    f"Stations block is not an object for '{state_name}/{district_name}'"
                )
                continue
            for station_name, station_id in stations.items():
                if station_id is None:
                    errors.append(
                        f"Missing station ID for '{state_name}/{district_name}/{station_name}'"
                    )
    return len(errors) == 0, errors


def build(
    delhi_path: Path,
    national_path: Path,
    output_path: Path,
    *,
    require_full_ids: bool,
    validate_only: bool,
) -> None:
    delhi = _load_json(delhi_path)
    national = _load_json(national_path)

    states_raw = delhi.get("states", {})
    states: dict[str, str] = {}
    if isinstance(states_raw, dict):
        states = {
            _as_clean_str(name).upper(): _as_clean_str(state_id)
            for name, state_id in states_raw.items()
        }

    by_state: dict[str, dict] = {}
    _merge_delhi(delhi, by_state)
    _merge_national(national, by_state)
    by_state = dict(sorted(by_state.items()))

    stats = _compute_stats(by_state)

    payload = {
        "_meta": {
            "schema_version": "1.0",
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "generated_by": "scripts/build_unified_stations_json.py",
            "sources": {
                "delhi": str(delhi_path.relative_to(REPO_ROOT)),
                "national": str(national_path.relative_to(REPO_ROOT)),
            },
            "stats": stats,
            "id_coverage": {
                "district_ids_complete": stats["districts_with_ids"] == stats["districts"],
                "station_ids_complete": stats["stations_with_ids"] == stats["stations"],
            },
        },
        "states": dict(sorted(states.items())),
        "by_state": by_state,
    }

    valid, errors = _validate_required_ids(payload)
    if require_full_ids and not valid:
        LOGGER.error(
            "Unified data failed full-ID validation with %d errors. "
            "Examples: %s",
            len(errors),
            errors[:5],
        )
        raise SystemExit(2)

    if validate_only:
        if valid:
            LOGGER.info("Validation passed: all district/station IDs are present.")
            return
        LOGGER.warning(
            "Validation found %d missing-ID issues. Examples: %s",
            len(errors),
            errors[:5],
        )
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    LOGGER.info(
        "Wrote %s — %d states, %d districts (%d with IDs), %d stations (%d with IDs)",
        output_path,
        stats["states"],
        stats["districts"],
        stats["districts_with_ids"],
        stats["stations"],
        stats["stations_with_ids"],
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delhi",
        type=Path,
        default=DEFAULT_DELHI,
        help="Path to Delhi source JSON",
    )
    parser.add_argument(
        "--national",
        type=Path,
        default=DEFAULT_NATIONAL,
        help="Path to national source JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Unified output JSON path",
    )
    parser.add_argument(
        "--require-full-ids",
        action="store_true",
        help="Fail if any district/station ID is missing.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Run ID validation without writing output.",
    )
    args = parser.parse_args()

    try:
        build(
            args.delhi.resolve(),
            args.national.resolve(),
            args.output.resolve(),
            require_full_ids=args.require_full_ids,
            validate_only=args.validate_only,
        )
    except FileNotFoundError as exc:
        LOGGER.error("%s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
