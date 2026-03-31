from __future__ import annotations

import io
import time

from aiogram import Bot

from core.stage_interface import PipelineStage
from infrastructure.groq_parser import GroqParser
from shared.audit_log import write_audit_event
from shared.models.session import FormSession, ImageRecord
from utils.aadhaar import mask_aadhaar, validate_aadhaar
from utils.payload_accessor import PayloadAccessor


class ImageParsingStage(PipelineStage):
    name = "parse_image"

    def __init__(self, groq_parser: GroqParser, bot: Bot) -> None:
        self._groq_parser = groq_parser
        self._bot = bot

    async def execute(self, session: FormSession) -> FormSession:
        person_records = [
            record
            for record in session.image_records
            if record.person == session.current_confirming_person
        ]

        if not person_records:
            raise ValueError(
                "No images uploaded. Please upload at least one ID image."
            )

        image_bytes_list: list[bytes] = []
        for record in person_records:
            buffer = io.BytesIO()
            await self._bot.download(record.image_id, destination=buffer)
            image_bytes_list.append(buffer.getvalue())

        parsed = await self._groq_parser.parse_image(image_bytes_list, "id_extraction")

        target_prefix = session.current_confirming_person

        raw_aadhaar = parsed.get("address_verification_doc_no")
        if raw_aadhaar:
            is_valid, cleaned_aadhaar = validate_aadhaar(str(raw_aadhaar))
            if not is_valid:
                session.last_error = (
                    "The Aadhaar number extracted from the uploaded image appears to be invalid. "
                    "Please upload a clearer image or correct it manually in the next step."
                )
                return session

            parsed["address_verification_doc_no"] = cleaned_aadhaar
            suffix = cleaned_aadhaar[-4:]

            for record in person_records:
                record.extracted_aadhaar_suffix = suffix

            other_person = "tenant" if session.current_confirming_person == "owner" else "owner"
            other_records = [
                r for r in session.image_records
                if r.person == other_person and r.extracted_aadhaar_suffix
            ]
            other_suffixes = {r.extracted_aadhaar_suffix for r in other_records}

            if suffix in other_suffixes:
                conflicting = person_records + [
                    r for r in other_records if r.extracted_aadhaar_suffix == suffix
                ]
                for record in conflicting:
                    write_audit_event(
                        "conflict_detected",
                        session.current_confirming_person,
                        record.image_id,
                        record,
                    )
                masked = mask_aadhaar(suffix)
                session.last_error = (
                    f"The same Aadhaar document ({masked}) appears to have been submitted "
                    "for both the owner and the tenant. Please re-upload the correct documents."
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
            PayloadAccessor.set(
                session.payload, "tenant.address_verification_doc_type", "Aadhar Card"
            )

        for record in person_records:
            write_audit_event(
                "image_processed",
                session.current_confirming_person,
                record.image_id,
                record,
            )

        return session
