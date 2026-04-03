from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StationLookup:
    """
    Reads data/delhi_police_stations.json and provides:
      - district names + portal values  (for picker UI + form_filler)
      - station names per district       (for picker UI)
      - station portal values            (for form_filler DOM writes)
      - state names + portal values      (for permanent address form_filler)
      - locality-based auto-suggest      (kept for backward compat with address parsing)
    """

    def __init__(self, stations_file: Path, legacy_file: Path | None = None) -> None:
        self._data = self._load_json(stations_file) if stations_file.exists() else {}
        self._legacy: list[dict[str, Any]] = (
            self._load_json_list(legacy_file) if legacy_file and legacy_file.exists() else []
        )

    @staticmethod
    def _load_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _load_json_list(path: Path) -> list:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []

    # ── District helpers ────────────────────────────────────────────────────

    def district_names(self) -> list[str]:
        """Sorted list of all Delhi district names for the picker UI."""
        return sorted(self._data.get("districts", {}).keys())

    def district_portal_value(self, district_name: str) -> str | None:
        """Return the portal integer value string for a district name, or None."""
        return self._data.get("districts", {}).get(district_name.strip().upper())

    # ── Station helpers ─────────────────────────────────────────────────────

    def stations_for_district(self, district: str) -> list[str]:
        """Sorted list of station names for a given district (for picker UI)."""
        key = self._normalize(district)
        for d_name, d_value in self._data.get("districts", {}).items():
            if self._normalize(d_name) == key:
                return sorted(self._data.get("stations", {}).get(d_name, {}).keys())
        return []

    def station_portal_value(self, district: str, station_name: str) -> str | None:
        """Return the portal integer value string for a station, or None."""
        key = self._normalize(district)
        for d_name in self._data.get("districts", {}):
            if self._normalize(d_name) == key:
                return self._data.get("stations", {}).get(d_name, {}).get(station_name)
        return None

    # ── State helpers ───────────────────────────────────────────────────────

    def state_portal_value(self, state_name: str) -> str | None:
        """Return the portal integer value string for an Indian state name, or None."""
        key = self._normalize(state_name)
        for s_name, s_value in self._data.get("states", {}).items():
            if self._normalize(s_name) == key:
                return s_value
        return None

    def state_names(self) -> list[str]:
        """Sorted list of all Indian state names."""
        return sorted(self._data.get("states", {}).keys())

    # ── Legacy locality-based auto-suggest ──────────────────────────────────

    def suggest(self, colony_locality_area: str | None, district: str | None = None) -> tuple[str | None, str | None]:
        """Map a locality string to (district, police_station) via legacy lookup file."""
        locality = (colony_locality_area or "").strip().lower()
        if locality:
            for row in self._legacy:
                if row.get("locality", "").strip().lower() == locality:
                    return row.get("district"), row.get("police_station")
        if district:
            return district, None
        return None, None

    # ── Internal ────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower().replace("-", " ")
