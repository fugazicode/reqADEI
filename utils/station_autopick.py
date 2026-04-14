from __future__ import annotations

import random
from typing import Iterable


def auto_pick_station(stations: Iterable[str]) -> str | None:
    candidates: list[str] = []
    for name in stations:
        if not name:
            continue
        cleaned = str(name).strip()
        if not cleaned:
            continue
        upper = cleaned.upper()
        if "SELECT" in upper or "NOT APPLICABLE" in upper:
            continue
        candidates.append(cleaned)
    if not candidates:
        return None
    return random.choice(candidates)
