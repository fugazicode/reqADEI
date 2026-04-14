from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Optional

from shared.models.form_payload import FormPayload


@dataclass
class ImageRecord:
    image_id: str
    person: str
    upload_timestamp: float = 0.0
    extracted_aadhaar_suffix: Optional[str] = None
    extraction_warnings: list[str] = field(default_factory=list)
    linked_to_image_id: Optional[str] = None
    media_group_id: Optional[str] = None


@dataclass
class FormSession:
    telegram_user_id: int

    payload: FormPayload = field(default_factory=FormPayload)

    image_records: list[ImageRecord] = field(default_factory=list)

    upload_status_message_id: Optional[int] = None

    # True while ID OCR pipeline runs (guards duplicate Extract / concurrent uploads).
    id_upload_extraction_in_progress: bool = False

    consent_given_at: Optional[float] = None

    # Second /start within 60s after warning discards in-progress session (FIX-7).
    pending_discard_start_at: Optional[float] = None

    tenant_image_bytes: bytes = field(default_factory=bytes)

    # Pipeline routing — used by ImageParsingStage to know which person to extract.
    # Values: "owner" | "tenant"
    current_confirming_person: str = "owner"

    # Edit tracking — set when user selects a field to edit from an overview.
    current_editing_field: Optional[str] = None

    # True when the user explicitly edits police station (skip auto-pick).
    station_picker_forced: bool = False

    # Message management
    # overview_message_id: the overview message edited in-place on every field update.
    overview_message_id: Optional[int] = None
    # last_prompt_message_id: picker or text-input prompt; deleted when edit completes.
    last_prompt_message_id: Optional[int] = None

    # Error from the last pipeline run.
    last_error: Optional[str] = None

    # Analytics DB row id — set by analytics_store.open_session().
    analytics_session_id: Optional[int] = None

    # ── Image record helpers ─────────────────────────────────────────────────

    @property
    def owner_image_file_ids(self) -> list[str]:
        return [r.image_id for r in self.image_records if r.person == "owner"]

    @owner_image_file_ids.setter
    def owner_image_file_ids(self, file_ids: list[str]) -> None:
        existing = {r.image_id for r in self.image_records if r.person == "owner"}
        for fid in file_ids:
            if fid not in existing:
                self.image_records.append(
                    ImageRecord(image_id=fid, person="owner", upload_timestamp=time.time())
                )
                existing.add(fid)

    @property
    def tenant_image_file_ids(self) -> list[str]:
        return [r.image_id for r in self.image_records if r.person == "tenant"]

    @tenant_image_file_ids.setter
    def tenant_image_file_ids(self, file_ids: list[str]) -> None:
        existing = {r.image_id for r in self.image_records if r.person == "tenant"}
        for fid in file_ids:
            if fid not in existing:
                self.image_records.append(
                    ImageRecord(image_id=fid, person="tenant", upload_timestamp=time.time())
                )
                existing.add(fid)
