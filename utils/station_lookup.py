from __future__ import annotations

import json
from pathlib import Path


class StationLookup:
    """
    Reads data/delhi_police_stations.json for Delhi-only flows (owner, tenanted premises)
    and optional data/national_police_stations.json for tenant permanent address
    (state → district → list of police station names).
    """

    def __init__(
        self,
        stations_file: Path,
        national_file: Path | None = None,
    ) -> None:
        self._data = self._load_json(stations_file) if stations_file.exists() else {}
        self._national: dict[str, dict[str, list[str]]] = {}
        nf = national_file
        if nf and nf.exists():
            raw = self._load_json(nf)
            block = raw.get("by_state", raw)
            if isinstance(block, dict):
                for k, v in block.items():
                    if k.startswith("_") or not isinstance(v, dict):
                        continue
                    self._national[str(k).strip().upper()] = self._normalize_national_block(v)

    @staticmethod
    def _normalize_national_block(v: dict) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for d_name, stations in v.items():
            if "SELECT" in str(d_name).upper():
                continue
            if isinstance(stations, list):
                cleaned = [
                    str(s).strip()
                    for s in stations
                    if "SELECT" not in str(s).upper()
                ]
                out[str(d_name).strip().upper()] = cleaned
            elif isinstance(stations, dict):
                keys = sorted(
                    k
                    for k in stations.keys()
                    if "SELECT" not in str(k).upper()
                )
                out[str(d_name).strip().upper()] = [str(k).strip() for k in keys]
        return out

    @staticmethod
    def _load_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    # ── District helpers (Delhi — owner / tenanted) ─────────────────────────

    def district_names(self) -> list[str]:
        """Sorted list of all Delhi district names for the picker UI."""
        return sorted(self._data.get("districts", {}).keys())

    def district_portal_value(self, district_name: str) -> str | None:
        """Return the portal integer value string for a district name, or None."""
        return self._data.get("districts", {}).get(district_name.strip().upper())

    # ── Station helpers (Delhi — owner / tenanted) ──────────────────────────

    def stations_for_district(self, district: str) -> list[str]:
        """Sorted list of station names for a given Delhi district (picker UI)."""
        key = self._normalize(district)
        for d_name, _ in self._data.get("districts", {}).items():
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

    # ── Permanent address (national, optional) ──────────────────────────────

    def _is_delhi_state(self, state_name: str) -> bool:
        n = self._normalize(state_name)
        return n in ("delhi", "nct of delhi", "national capital territory of delhi")

    def _resolve_national_state_key(self, state_name: str) -> str | None:
        """Match user / portal state label to a key in national JSON."""
        target = self._normalize(state_name)
        for key in self._national:
            if self._normalize(key) == target:
                return key
        return None

    def districts_for_perm_addr(self, state_name: str) -> list[str]:
        """District names for tenant permanent address, given selected state."""
        if self._is_delhi_state(state_name):
            return self.district_names()
        sk = self._resolve_national_state_key(state_name)
        if not sk:
            return []
        return sorted(self._national[sk].keys())

    def stations_for_perm_addr(self, state_name: str, district: str) -> list[str]:
        """Police stations for tenant permanent address."""
        if self._is_delhi_state(state_name):
            return self.stations_for_district(district)
        sk = self._resolve_national_state_key(state_name)
        if not sk:
            return []
        d_key = self._resolve_district_key(self._national[sk], district)
        if not d_key:
            return []
        return sorted(self._national[sk][d_key])

    def _resolve_district_key(self, state_block: dict[str, list[str]], district: str) -> str | None:
        target = self._normalize(district)
        for d_name in state_block:
            if self._normalize(d_name) == target:
                return d_name
        return None

    # ── State helpers (Indian states — portal ids from Delhi JSON) ─────────

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

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower().replace("-", " ")
