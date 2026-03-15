from __future__ import annotations

import json
import time

from shared.models.session import ImageRecord


def write_audit_event(event_type: str, person: str, image_id: str, record: ImageRecord) -> None:
    event = {
        "event_type": event_type,
        "person": person,
        "image_id": image_id,
        "timestamp": time.time(),
        "side": record.side,
        "aadhaar_suffix": record.extracted_aadhaar_suffix if record.extracted_aadhaar_suffix else None,
        "ocr_confidence": record.ocr_confidence,
        "qr_decoded": record.qr_decoded,
        "extraction_warnings": record.extraction_warnings,
        "upload_timestamp": record.upload_timestamp,
        "linked_to_image_id": record.linked_to_image_id,
    }

    with open("audit.log", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event))
        handle.write("\n")
