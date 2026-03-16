from __future__ import annotations

import re


# Verhoeff algorithm tables as published in Verhoeff, J. (1969). Error Detecting Decimal Codes.
# These values must not be modified. The multiplication table d is 10x10, the permutation table p
# is 8x10 (indexed by position mod 8), and inv is the dihedral group inverse table.
d = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

p = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

inv = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def _apply_ocr_substitutions(value: str) -> str:
    return (
        value.replace("O", "0")
        .replace("I", "1")
        .replace("l", "1")
        .replace("S", "5")
        .replace("B", "8")
    )


def _verhoeff_checksum(number: str) -> bool:
    c = 0
    for i, digit in enumerate(reversed(number)):
        c = d[c][p[i % 8][int(digit)]]
    return c == 0


def validate_aadhaar(number: str) -> tuple[bool, str]:
    cleaned = re.sub(r"[\s-]+", "", number)
    cleaned = _apply_ocr_substitutions(cleaned)

    if len(cleaned) != 12 or not cleaned.isdigit():
        return False, ""

    if cleaned[0] not in "23456789":
        return False, ""

    if len(set(cleaned)) == 1:
        return False, ""

    if cleaned == "123456789012":
        return False, ""

    if not _verhoeff_checksum(cleaned):
        return False, ""

    return True, cleaned


def extract_aadhaar_from_text(ocr_text: str) -> list[str]:
    substituted = _apply_ocr_substitutions(ocr_text)
    stripped = re.sub(r"[\s-]+", "", substituted)
    candidates = re.findall(r"\d{12,}", stripped)
    found: list[str] = []
    seen: set[str] = set()

    for raw in candidates:
        if len(raw) == 12:
            windows = [raw]
        else:
            start = raw[:12]
            end = raw[-12:]
            windows = [start, end] if start != end else [start]

        for candidate in windows:
            is_valid, cleaned = validate_aadhaar(candidate)
            if is_valid and cleaned not in seen:
                found.append(cleaned)
                seen.add(cleaned)

    return found


def mask_aadhaar(number: str) -> str:
    """Accept a full 12-digit Aadhaar or a 4-digit suffix."""
    cleaned = re.sub(r"[\s-]+", "", number)
    if len(cleaned) == 4 and cleaned.isdigit():
        return f"XXXX-XXXX-{cleaned}"
    if len(cleaned) == 12 and cleaned.isdigit():
        return f"XXXX-XXXX-{cleaned[-4:]}"
    return "XXXX-XXXX-XXXX"


def classify_side(ocr_text: str, qr_decoded: bool) -> str:
    if qr_decoded:
        return "back"

    indicators = [
        "address",
        "s/o",
        "d/o",
        "w/o",
        "c/o",
        "near",
        "village",
        "district",
        "pin",
    ]

    indicator_hits = sum(
        1
        for indicator in indicators
        if re.search(r"\b" + re.escape(indicator) + r"\b", ocr_text, re.IGNORECASE)
    )

    dob_pattern = re.compile(r"\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2})\b")
    name_pattern = re.compile(r"\b[A-Z][a-zA-Z]{1,}(?:\s+[A-Z][a-zA-Z]{1,})+\b")

    has_dob = bool(dob_pattern.search(ocr_text))
    has_name = bool(name_pattern.search(ocr_text))

    if not has_dob and indicator_hits >= 2:
        return "back"

    if has_dob and has_name:
        return "front"

    return "unknown"
