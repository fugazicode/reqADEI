"""Persist and restore SubmissionInput for offline Playwright testing."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from shared.models.form_payload import FormPayload
from shared.models.submission_input import SubmissionInput

MANIFEST_NAME = "manifest.json"
IMAGE_NAME = "tenant_image.jpg"
LEGACY_IMAGE_NAME = "tenant_image.bin"
SCHEMA_VERSION = 2


def _resolve_image_path(directory: Path) -> Path:
    jpg = directory / IMAGE_NAME
    if jpg.is_file():
        return jpg
    legacy = directory / LEGACY_IMAGE_NAME
    if legacy.is_file():
        return legacy
    raise FileNotFoundError(
        f"Missing tenant image (expected {IMAGE_NAME} or {LEGACY_IMAGE_NAME} in {directory})"
    )


def save_snapshot(directory: Path, inp: SubmissionInput) -> Path:
    """Write manifest.json and tenant_image.jpg under a timestamped subdirectory.

    ``directory`` is the per-user folder (e.g. data/submission_snapshot/<telegram_user_id>).
    Each call creates a new subdirectory so previous snapshots are never overwritten.
    Returns the run directory that was written.
    """
    directory.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    run_dir = directory / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "telegram_user_id": inp.telegram_user_id,
        "payload": inp.payload.model_dump(mode="json"),
    }
    (run_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / IMAGE_NAME).write_bytes(inp.image_bytes)
    return run_dir


def load_snapshot(directory: Path) -> SubmissionInput:
    """Load a snapshot from a specific run directory.

    Pass the timestamped subdirectory directly, e.g.:
        data/submission_snapshot/123456789/2026-04-09_14-32-01_123456
    Legacy v1 layouts in that same folder (manifest + tenant_image.bin) also load.
    """
    manifest_path = directory / MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")

    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = raw.get("schema_version")
    if version not in (1, 2):
        raise ValueError(
            f"Unsupported snapshot schema_version {version!r}; expected 1 or 2"
        )

    image_path = _resolve_image_path(directory)
    payload = FormPayload.model_validate(raw["payload"])
    return SubmissionInput(
        telegram_user_id=int(raw["telegram_user_id"]),
        payload=payload,
        image_bytes=image_path.read_bytes(),
    )
