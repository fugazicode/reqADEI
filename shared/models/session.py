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

    consent_given_at: Optional[float] = None

    tenant_image_bytes: bytes = field(default_factory=bytes)

    # Ordered field paths still awaiting user confirmation.
    confirmation_queue: list[str] = field(default_factory=list)

    # Dot-notation path currently being edited by the user.
    current_editing_field: Optional[str] = None

    # Must be set by handlers before triggering a pipeline run.
    current_confirming_person: str = "owner"

    # Handler-controlled routing to the next workflow stage.
    next_stage: Optional[str] = None

    # One-level edit stack for returning from edit input.
    edit_return_state: Optional[str] = None
    edit_return_person: Optional[str] = None

    # Set by the pipeline engine whenever a stage fails.
    last_error: Optional[str] = None

    # These properties are intentionally excluded from dataclasses.fields() and dataclasses.asdict().
    # If FormSession is ever serialized using dataclass introspection tools, owner and tenant file IDs
    # will not be included. Use session.image_records directly for serialization.
    @property
    def owner_image_file_ids(self) -> list[str]:
        return [record.image_id for record in self.image_records if record.person == "owner"]

    @owner_image_file_ids.setter
    def owner_image_file_ids(self, file_ids: list[str]) -> None:
        existing_ids = {record.image_id for record in self.image_records if record.person == "owner"}
        for file_id in file_ids:
            if file_id in existing_ids:
                continue
            self.image_records.append(
                ImageRecord(
                    image_id=file_id,
                    person="owner",
                    upload_timestamp=time.time(),
                )
            )

    @property
    def tenant_image_file_ids(self) -> list[str]:
        return [record.image_id for record in self.image_records if record.person == "tenant"]

    @tenant_image_file_ids.setter
    def tenant_image_file_ids(self, file_ids: list[str]) -> None:
        existing_ids = {record.image_id for record in self.image_records if record.person == "tenant"}
        for file_id in file_ids:
            if file_id in existing_ids:
                continue
            self.image_records.append(
                ImageRecord(
                    image_id=file_id,
                    person="tenant",
                    upload_timestamp=time.time(),
                )
            )
