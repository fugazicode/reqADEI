from __future__ import annotations

import io
import time

from aiogram import Bot

from core.stage_interface import PipelineStage
from infrastructure.groq_parser import GroqParser
from infrastructure.vision_client import VisionClient
from shared.audit_log import write_audit_event
from shared.models.session import FormSession, ImageRecord
from utils.aadhaar import classify_side, extract_aadhaar_from_text, mask_aadhaar
from utils.payload_accessor import PayloadAccessor


class ImageExtractionStage(PipelineStage):
    name = "extract_images"

    def __init__(self, vision_client: VisionClient, bot: Bot) -> None:
        self._vision_client = vision_client
        self._bot = bot

    async def execute(self, session: FormSession) -> FormSession:
        session.raw_ocr_text = ""
        person_records = [
            record for record in session.image_records if record.person == session.current_confirming_person
        ]
        file_ids = [record.image_id for record in person_records]

        extracted_texts: list[str] = []
        for file_id in file_ids:
            record = next(
                (
                    entry
                    for entry in session.image_records
                    if entry.image_id == file_id and entry.person == session.current_confirming_person
                ),
                None,
            )
            if record is None:
                record = ImageRecord(
                    image_id=file_id,
                    person=session.current_confirming_person,
                    upload_timestamp=time.time(),
                )
                session.image_records.append(record)

            buffer = io.BytesIO()
            await self._bot.download(file_id, destination=buffer)
            image_bytes = buffer.getvalue()
            extracted_text = await self._vision_client.extract_text(image_bytes)
            extracted_texts.append(extracted_text)

            candidates = extract_aadhaar_from_text(extracted_text)
            record.side = classify_side(extracted_text, qr_decoded=False)

            if len(candidates) == 1:
                record.extracted_aadhaar_suffix = candidates[0][-4:]
                record.ocr_confidence = 0.85
            elif len(candidates) == 0:
                record.ocr_confidence = 0.2
                record.extraction_warnings.append("no_aadhaar_found")
            else:
                record.ocr_confidence = 0.5
                record.extraction_warnings.append("multiple_candidates")

            write_audit_event(
                "image_processed",
                session.current_confirming_person,
                record.image_id,
                record,
            )

        session.raw_ocr_text = "\n---\n".join(filter(None, extracted_texts))

        person_records = [
            record for record in session.image_records if record.person == session.current_confirming_person
        ]
        suffix_records = [
            record for record in person_records if record.extracted_aadhaar_suffix is not None
        ]
        unique_suffixes = {record.extracted_aadhaar_suffix for record in suffix_records}
        if len(unique_suffixes) > 1 and all(
            record.ocr_confidence >= 0.85 for record in suffix_records
        ):
            masked = []
            seen = set()
            for record in suffix_records:
                suffix = record.extracted_aadhaar_suffix
                if suffix and suffix not in seen:
                    masked.append(mask_aadhaar(suffix))
                    seen.add(suffix)
            session.last_error = (
                "Two different Aadhaar documents were detected for the same person ("
                + " and ".join(masked)
                + "). Please re-upload the correct images."
            )
            return session

        media_group_records = [
            record for record in person_records if record.media_group_id is not None
        ]
        media_group_map: dict[str, list[ImageRecord]] = {}
        for record in media_group_records:
            media_group_map.setdefault(record.media_group_id, []).append(record)
        for records in media_group_map.values():
            if len(records) == 2:
                first, second = records
                first.linked_to_image_id = second.image_id
                second.linked_to_image_id = first.image_id

        fronts = [record for record in person_records if record.side == "front"]
        backs = [record for record in person_records if record.side == "back"]
        used_back_ids: set[str] = set()
        for front in fronts:
            if front.linked_to_image_id:
                continue
            for back in backs:
                if back.linked_to_image_id:
                    continue
                if back.image_id in used_back_ids:
                    continue
                if (
                    front.extracted_aadhaar_suffix
                    and back.extracted_aadhaar_suffix
                    and front.extracted_aadhaar_suffix == back.extracted_aadhaar_suffix
                ):
                    front.linked_to_image_id = back.image_id
                    back.linked_to_image_id = front.image_id
                    used_back_ids.add(back.image_id)
                    break

        if len(fronts) == 1 and len(backs) == 1:
            front = fronts[0]
            back = backs[0]
            if not front.linked_to_image_id and not back.linked_to_image_id:
                front.linked_to_image_id = back.image_id
                back.linked_to_image_id = front.image_id
                front.extraction_warnings.append("linked_by_position")
                back.extraction_warnings.append("linked_by_position")

        return session


class IdParsingStage(PipelineStage):
    name = "parse_id"

    def __init__(self, groq_parser: GroqParser) -> None:
        self._groq_parser = groq_parser

    async def execute(self, session: FormSession) -> FormSession:
        if not session.raw_ocr_text.strip():
            raise ValueError("No text could be extracted from uploaded images. Please upload a clearer, front-facing ID image.")

        parsed = await self._groq_parser.parse(session.raw_ocr_text, "id_extraction")
        target_prefix = "owner" if session.current_confirming_person == "owner" else "tenant"

        current_records = [
            record
            for record in session.image_records
            if record.person == session.current_confirming_person and record.extracted_aadhaar_suffix
        ]
        other_person = "tenant" if session.current_confirming_person == "owner" else "owner"
        other_records = [
            record
            for record in session.image_records
            if record.person == other_person and record.extracted_aadhaar_suffix
        ]
        current_suffixes = {record.extracted_aadhaar_suffix for record in current_records}
        other_suffixes = {record.extracted_aadhaar_suffix for record in other_records}
        overlap = current_suffixes.intersection(other_suffixes)
        if overlap:
            for record in current_records + other_records:
                if record.extracted_aadhaar_suffix in overlap:
                    write_audit_event(
                        "conflict_detected",
                        session.current_confirming_person,
                        record.image_id,
                        record,
                    )
            session.last_error = (
                "The same Aadhaar document appears to have been submitted for both the owner and the tenant. "
                "Please re-upload the correct documents."
            )
            return session

        for key, value in parsed.items():
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    PayloadAccessor.set(
                        session.payload,
                        f"{target_prefix}.{key}.{nested_key}",
                        nested_value,
                    )
            else:
                PayloadAccessor.set(session.payload, f"{target_prefix}.{key}", value)

        if target_prefix == "tenant" and not PayloadAccessor.get(
            session.payload,
            "tenant.address_verification_doc_type",
        ):
            PayloadAccessor.set(session.payload, "tenant.address_verification_doc_type", "Aadhar Card")

        return session
