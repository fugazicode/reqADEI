from __future__ import annotations

import json
import logging
from pathlib import Path
import time

from shared.models.session import ImageRecord


_audit_log_path = Path(__file__).resolve().parent.parent / "audit.log"
_audit_logger = logging.getLogger("audit")
_audit_logger.setLevel(logging.DEBUG)
if not _audit_logger.handlers:
    _handler = logging.FileHandler(_audit_log_path, encoding="utf-8")
    _handler.setLevel(logging.DEBUG)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _audit_logger.addHandler(_handler)
    _audit_logger.propagate = False


def write_audit_event(event_type: str, person: str, image_id: str, record: ImageRecord) -> None:
    event = {
        "event_type": event_type,
        "person": person,
        "image_id": image_id,
        "timestamp": time.time(),
        "aadhaar_suffix": record.extracted_aadhaar_suffix if record.extracted_aadhaar_suffix else None,
        "extraction_warnings": record.extraction_warnings,
        "upload_timestamp": record.upload_timestamp,
        "linked_to_image_id": record.linked_to_image_id,
    }

    _audit_logger.info(json.dumps(event))
