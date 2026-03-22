from dataclasses import dataclass, asdict
from pathlib import Path
import json
import time
from typing import List, Optional

@dataclass
class RefundEntry:
    charge_id: str
    user_id: int
    request_number: str
    paid_at: float
    status: str  # "eligible" | "requested" | "approved" | "rejected"
    reason: str = ""
    test_mode: bool = False

class RefundLedger:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: List[RefundEntry] = []
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            with self._path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                self._entries = [RefundEntry(**entry) for entry in data]
        else:
            self._entries = []

    def add(self, entry: RefundEntry) -> None:
        self._entries.append(entry)
        self._save()

    def get_latest_eligible(self, user_id: int) -> Optional[RefundEntry]:
        eligible = [e for e in self._entries if e.user_id == user_id and e.status in ("eligible", "requested")]
        if not eligible:
            return None
        return max(eligible, key=lambda e: e.paid_at)

    def get_by_charge_id(self, charge_id: str) -> Optional[RefundEntry]:
        for e in self._entries:
            if e.charge_id == charge_id:
                return e
        return None

    def update_status(self, charge_id: str, status: str, reason: str = "") -> bool:
        for e in self._entries:
            if e.charge_id == charge_id:
                e.status = status
                e.reason = reason
                self._save()
                return True
        return False

    def _save(self) -> None:
        tmp_path = self._path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump([asdict(e) for e in self._entries], f, ensure_ascii=False, indent=2)
        tmp_path.replace(self._path)
