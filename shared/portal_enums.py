from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OptionSet:
    values: tuple[str, ...]
    aliases: dict[str, str]

    def normalize(self, raw_value: str | None) -> str | None:
        if not raw_value:
            return raw_value
        cleaned = " ".join(raw_value.strip().split())
        if not cleaned:
            return cleaned
        alias_key = cleaned.upper()
        if alias_key in self.aliases:
            return self.aliases[alias_key]
        return cleaned


OWNER_OCCUPATIONS = OptionSet(
    values=(
        "ACADEMICIAN",
        "BANK EMPLOYEE",
        "BUSINESS",
        "COMPANY EXECUTIVE",
    ),
    aliases={
        "PRIVATE SERVICE": "COMPANY EXECUTIVE",
        "PVT SERVICE": "COMPANY EXECUTIVE",
    },
)

TENANCY_PURPOSES = OptionSet(
    values=(
        "Residential",
        "commercial",
    ),
    aliases={
        "RESIDENTIAL": "Residential",
        "COMMERCIAL": "commercial",
        "BUSINESS": "commercial",
        "OFFICE": "commercial",
    },
)
