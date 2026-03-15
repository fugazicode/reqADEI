from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from shared.models.form_payload import FormPayload


@dataclass
class FormSession:
    telegram_user_id: int

    payload: FormPayload = field(default_factory=FormPayload)

    owner_image_file_ids: list[str] = field(default_factory=list)
    tenant_image_file_ids: list[str] = field(default_factory=list)

    # Stores concatenated OCR text between extraction and parsing stages.
    raw_ocr_text: str = ""

    # Ordered field paths still awaiting user confirmation.
    confirmation_queue: list[str] = field(default_factory=list)

    # Dot-notation path currently being edited by the user.
    current_editing_field: Optional[str] = None

    # Must be set by handlers before triggering a pipeline run.
    current_confirming_person: str = "owner"

    # Set by the pipeline engine whenever a stage fails.
    last_error: Optional[str] = None
