from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StationLookup:
    """
        Unified-first police station lookup.

        Priority order:
            1) data/police_stations.json (unified)
            2) data/delhi_police_stations.json (legacy Delhi)
            3) data/national_police_stations.json (legacy national)

        This keeps existing runtime behavior stable while migration is in progress.
    """

    def __init__(
        self,
        stations_file: Path,
        national_file: Path | None = None,
        unified_file: Path | None = None,
    ) -> None:
        self._legacy_delhi = self._load_json(stations_file) if stations_file.exists() else {}
        self._legacy_national: dict[str, dict[str, list[str]]] = {}
        self._unified_states: dict[str, str] = {}
        self._unified_by_state: dict[str, dict[str, dict[str, Any]]] = {}

        nf = national_file
        if nf and nf.exists():
            raw = self._load_json(nf)
            block = raw.get("by_state", raw)
            if isinstance(block, dict):
                for k, v in block.items():
                    if k.startswith("_") or not isinstance(v, dict):
                        continue
                    self._legacy_national[str(k).strip().upper()] = self._normalize_national_block(v)

        uf = unified_file
        if uf and uf.exists():
            raw = self._load_json(uf)
            self._unified_states = self._normalize_unified_states(raw.get("states", {}))
            self._unified_by_state = self._normalize_unified_by_state(raw.get("by_state", {}))

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
    def _normalize_unified_states(v: object) -> dict[str, str]:
        out: dict[str, str] = {}
        if not isinstance(v, dict):
            return out
        for state_name, state_id in v.items():
            s_name = str(state_name).strip().upper()
            if not s_name or s_name.startswith("_"):
                continue
            cleaned = StationLookup._clean_optional_id(state_id)
            if cleaned is None:
                continue
            out[s_name] = cleaned
        return out

    @staticmethod
    def _normalize_unified_by_state(v: object) -> dict[str, dict[str, dict[str, Any]]]:
        out: dict[str, dict[str, dict[str, Any]]] = {}
        if not isinstance(v, dict):
            return out

        for state_name, districts_raw in v.items():
            s_name = str(state_name).strip().upper()
            if not s_name or s_name.startswith("_") or not isinstance(districts_raw, dict):
                continue

            state_block: dict[str, dict[str, Any]] = {}
            for district_name, district_entry_raw in districts_raw.items():
                d_name = str(district_name).strip().upper()
                if not d_name or "SELECT" in d_name or not isinstance(district_entry_raw, dict):
                    continue

                district_id = StationLookup._clean_optional_id(
                    district_entry_raw.get("district_id")
                )
                stations_raw = district_entry_raw.get("stations", {})
                stations: dict[str, str | None] = {}

                if isinstance(stations_raw, dict):
                    for station_name, station_id in stations_raw.items():
                        s_name_clean = str(station_name).strip()
                        if not s_name_clean or "SELECT" in s_name_clean.upper():
                            continue
                        stations[s_name_clean] = StationLookup._clean_optional_id(station_id)
                elif isinstance(stations_raw, list):
                    for station_name in stations_raw:
                        s_name_clean = str(station_name).strip()
                        if not s_name_clean or "SELECT" in s_name_clean.upper():
                            continue
                        stations[s_name_clean] = None

                state_block[d_name] = {
                    "district_id": district_id,
                    "stations": dict(sorted(stations.items())),
                }

            out[s_name] = dict(sorted(state_block.items()))

        return out

    @staticmethod
    def _clean_optional_id(value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @staticmethod
    def _load_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _resolve_unified_state_key(self, state_name: str) -> str | None:
        target = self._normalize(state_name)
        for key in self._unified_by_state:
            if self._normalize(key) == target:
                return key
        return None

    def _delhi_unified_block(self) -> dict[str, dict[str, Any]]:
        return self._unified_by_state.get("DELHI", {})

    # ── District helpers (Delhi — owner / tenanted) ─────────────────────────

    def district_names(self) -> list[str]:
        """Sorted list of all Delhi district names for the picker UI."""
        delhi_block = self._delhi_unified_block()
        if delhi_block:
            return sorted(delhi_block.keys())
        return sorted(self._legacy_delhi.get("districts", {}).keys())

    def district_portal_value(self, district_name: str) -> str | None:
        """Return the portal integer value string for a district name, or None."""
        delhi_block = self._delhi_unified_block()
        if delhi_block:
            d_key = self._resolve_district_key(delhi_block, district_name)
            if d_key:
                return self._clean_optional_id(delhi_block[d_key].get("district_id"))
        return self._legacy_delhi.get("districts", {}).get(district_name.strip().upper())

    # ── Station helpers (Delhi — owner / tenanted) ──────────────────────────

    def stations_for_district(self, district: str) -> list[str]:
        """Sorted list of station names for a given Delhi district (picker UI)."""
        delhi_block = self._delhi_unified_block()
        if delhi_block:
            d_key = self._resolve_district_key(delhi_block, district)
            if not d_key:
                return []
            stations = delhi_block[d_key].get("stations", {})
            if isinstance(stations, dict):
                return sorted(stations.keys())
            return []

        key = self._normalize(district)
        for d_name, _ in self._legacy_delhi.get("districts", {}).items():
            if self._normalize(d_name) == key:
                return sorted(self._legacy_delhi.get("stations", {}).get(d_name, {}).keys())
        return []

    def station_portal_value(self, district: str, station_name: str) -> str | None:
        """Return the portal integer value string for a station, or None."""
        delhi_block = self._delhi_unified_block()
        if delhi_block:
            d_key = self._resolve_district_key(delhi_block, district)
            if d_key:
                stations = delhi_block[d_key].get("stations", {})
                if isinstance(stations, dict):
                    s_key = self._resolve_station_key(stations, station_name)
                    if s_key:
                        return self._clean_optional_id(stations.get(s_key))

        key = self._normalize(district)
        for d_name in self._legacy_delhi.get("districts", {}):
            if self._normalize(d_name) == key:
                station_map = self._legacy_delhi.get("stations", {}).get(d_name, {})
                if station_name in station_map:
                    return station_map.get(station_name)
                s_key = self._resolve_station_key(station_map, station_name)
                if s_key:
                    return station_map.get(s_key)
        return None

    # ── Permanent address (national, optional) ──────────────────────────────

    def _is_delhi_state(self, state_name: str) -> bool:
        n = self._normalize(state_name)
        return n in ("delhi", "nct of delhi", "national capital territory of delhi")

    def _resolve_national_state_key(self, state_name: str) -> str | None:
        """Match user / portal state label to a key in national JSON."""
        if self._unified_by_state:
            key = self._resolve_unified_state_key(state_name)
            if key and not self._is_delhi_state(key):
                return key

        target = self._normalize(state_name)
        for key in self._legacy_national:
            if self._normalize(key) == target:
                return key
        return None

    def districts_for_perm_addr(self, state_name: str) -> list[str]:
        """District names for tenant permanent address, given selected state."""
        if self._is_delhi_state(state_name):
            return self.district_names()

        if self._unified_by_state:
            sk = self._resolve_national_state_key(state_name)
            if not sk:
                return []
            return sorted(self._unified_by_state.get(sk, {}).keys())

        sk = self._resolve_national_state_key(state_name)
        if not sk:
            return []
        return sorted(self._legacy_national[sk].keys())

    def stations_for_perm_addr(self, state_name: str, district: str) -> list[str]:
        """Police stations for tenant permanent address."""
        if self._is_delhi_state(state_name):
            return self.stations_for_district(district)

        if self._unified_by_state:
            sk = self._resolve_national_state_key(state_name)
            if not sk:
                return []
            state_block = self._unified_by_state.get(sk, {})
            d_key = self._resolve_district_key(state_block, district)
            if not d_key:
                return []
            stations = state_block[d_key].get("stations", {})
            if isinstance(stations, dict):
                return sorted(stations.keys())
            return []

        sk = self._resolve_national_state_key(state_name)
        if not sk:
            return []
        d_key = self._resolve_district_key(self._legacy_national[sk], district)
        if not d_key:
            return []
        return sorted(self._legacy_national[sk][d_key])

    def _resolve_district_key(self, state_block: dict[str, Any], district: str) -> str | None:
        target = self._normalize(district)
        for d_name in state_block:
            if self._normalize(d_name) == target:
                return d_name
        return None

    def _resolve_station_key(self, stations: dict[str, Any], station_name: str) -> str | None:
        target = self._normalize(station_name)
        for s_name in stations:
            if self._normalize(s_name) == target:
                return s_name
        return None

    # ── State helpers (Indian states — portal ids from Delhi JSON) ─────────

    def state_portal_value(self, state_name: str) -> str | None:
        """Return the portal integer value string for an Indian state name, or None."""
        if self._unified_states:
            key = self._normalize(state_name)
            for s_name, s_value in self._unified_states.items():
                if self._normalize(s_name) == key:
                    return self._clean_optional_id(s_value)

        key = self._normalize(state_name)
        for s_name, s_value in self._legacy_delhi.get("states", {}).items():
            if self._normalize(s_name) == key:
                return s_value
        return None

    def state_names(self) -> list[str]:
        """Sorted list of all Indian state names."""
        if self._unified_states:
            return sorted(self._unified_states.keys())
        return sorted(self._legacy_delhi.get("states", {}).keys())

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().lower().replace("-", " ")
