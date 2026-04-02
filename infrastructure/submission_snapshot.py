"""Persist and restore `SubmissionInput` for offline Playwright testing (no Telegram bot)."""

from __future__ import annotations

import json
from pathlib import Path

from shared.models.form_payload import FormPayload
from shared.models.submission_input import SubmissionInput

MANIFEST_NAME = "manifest.json"
IMAGE_NAME = "tenant_image.bin"
SCHEMA_VERSION = 1


def save_snapshot(directory: Path, inp: SubmissionInput) -> None:
    """Write `manifest.json` (payload + metadata) and `tenant_image.bin` under ``directory``."""
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "telegram_user_id": inp.telegram_user_id,
        "payload": inp.payload.model_dump(mode="json"),
    }
    (directory / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (directory / IMAGE_NAME).write_bytes(inp.image_bytes)


def load_snapshot(directory: Path) -> SubmissionInput:
    """Load a snapshot written by :func:`save_snapshot`."""
    manifest_path = directory / MANIFEST_NAME
    image_path = directory / IMAGE_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")
    if not image_path.is_file():
        raise FileNotFoundError(f"Missing tenant image: {image_path}")

    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"Unsupported snapshot schema_version {version!r}; expected {SCHEMA_VERSION}")

    payload = FormPayload.model_validate(raw["payload"])
    return SubmissionInput(
        telegram_user_id=int(raw["telegram_user_id"]),
        payload=payload,
        image_bytes=image_path.read_bytes(),
    )
