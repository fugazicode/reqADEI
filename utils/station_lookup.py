from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StationLookup:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._records = self._load_records()

    def _load_records(self) -> list[dict[str, Any]]:
        if not self._file_path.exists():
            return []
        return json.loads(self._file_path.read_text(encoding="utf-8"))

    def suggest(self, colony_locality_area: str | None, district: str | None = None) -> tuple[str | None, str | None]:
        locality = (colony_locality_area or "").strip().lower()
        if locality:
            for row in self._records:
                if row.get("locality", "").strip().lower() == locality:
                    return row.get("district"), row.get("police_station")

        if district:
            return district, None

        return None, None

    def stations_for_district(self, district: str) -> list[str]:
        normalized = self._normalize_district(district)
        return sorted(
            {
                row.get("police_station", "")
                for row in self._records
                if self._normalize_district(row.get("district", "")) == normalized and row.get("police_station")
            }
        )

    @staticmethod
    def _normalize_district(value: str) -> str:
        return value.strip().lower().replace("-", " ")
