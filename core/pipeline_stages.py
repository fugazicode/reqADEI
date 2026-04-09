from __future__ import annotations

import io
import logging

from aiogram import Bot

from core.stage_interface import PipelineStage
from infrastructure.analytics_store import AnalyticsStore
from infrastructure.groq_parser import GroqParser
from shared.audit_log import write_audit_event
from shared.models.session import FormSession, ImageRecord
from shared.portal_enums import STATES
from utils.aadhaar import mask_aadhaar, validate_aadhaar
from utils.payload_accessor import PayloadAccessor

# Must match keys in features/submission/form_filler.py DISTRICT_VALUES.
_DELHI_DISTRICT_KEYS: frozenset[str] = frozenset(
    {
        "CENTRAL",
        "DWARKA",
        "EAST",
        "IGI AIRPORT",
        "NEW DELHI",
        "NORTH",
        "NORTH EAST",
        "NORTH WEST",
        "OUTER DISTRICT",
        "OUTER NORTH",
        "ROHINI",
        "SHAHDARA",
        "SOUTH",
        "SOUTH WEST",
        "SOUTH-EAST",
        "WEST",
    }
)

# OCR / colloquial variants -> canonical portal district key (uppercase).
_DELHI_DISTRICT_ALIASES: dict[str, str] = {
    "SOUTH DELHI": "SOUTH",
    "SOUTH DELHI DISTRICT": "SOUTH",
    "NORTH DELHI": "NORTH",
    "NORTH DELHI DISTRICT": "NORTH",
    "EAST DELHI": "EAST",
    "EAST DELHI DISTRICT": "EAST",
    "WEST DELHI": "WEST",
    "WEST DELHI DISTRICT": "WEST",
    "CENTRAL DELHI": "CENTRAL",
    "CENTRAL DELHI DISTRICT": "CENTRAL",
    "NEW DELHI DISTRICT": "NEW DELHI",
    "NORTH EAST DELHI": "NORTH EAST",
    "NORTH-EAST DELHI": "NORTH EAST",
    "NORTH EAST DISTRICT": "NORTH EAST",
    "NORTH WEST DELHI": "NORTH WEST",
    "NORTH-WEST DELHI": "NORTH WEST",
    "NORTH WEST DISTRICT": "NORTH WEST",
    "SOUTH EAST DELHI": "SOUTH-EAST",
    "SOUTH-EAST DELHI": "SOUTH-EAST",
    "SOUTH EAST": "SOUTH-EAST",
    "SOUTH EAST DISTRICT": "SOUTH-EAST",
    "SOUTH-WEST DELHI": "SOUTH WEST",
    "SOUTH WEST DELHI": "SOUTH WEST",
    "SOUTH WEST DISTRICT": "SOUTH WEST",
    "OUTER DELHI": "OUTER DISTRICT",
    "OUTER DISTRICT DELHI": "OUTER DISTRICT",
    "INDIRA GANDHI INTERNATIONAL": "IGI AIRPORT",
    "INDIRA GANDHI INTERNATIONAL AIRPORT": "IGI AIRPORT",
}


def _normalise_delhi_district(raw: str) -> str:
    """Map OCR district text to a DISTRICT_VALUES key; else return collapsed UPPERCASE."""
    collapsed = " ".join(str(raw).strip().split()).upper()
    if collapsed in _DELHI_DISTRICT_KEYS:
        return collapsed
    if collapsed in _DELHI_DISTRICT_ALIASES:
        return _DELHI_DISTRICT_ALIASES[collapsed]
    return collapsed


class ImageParsingStage(PipelineStage):
    name = "parse_image"

    def __init__(
        self,
        groq_parser: GroqParser,
        bot: Bot,
        analytics_store: AnalyticsStore | None = None,
    ) -> None:
        self._groq_parser = groq_parser
        self._bot = bot
        self._analytics = analytics_store
        self._logger = logging.getLogger(__name__)

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

        if session.current_confirming_person == "tenant" and image_bytes_list:
            session.tenant_image_bytes = image_bytes_list[0]

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
                await self._log_extraction(session, image_bytes_list, parsed, session.last_error, False)
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
                await self._log_extraction(session, image_bytes_list, parsed, session.last_error, False)
                return session

        for key, value in parsed.items():
            if isinstance(value, dict):
                for nested_key, nested_value in value.items():
                    if nested_value is not None:
                        PayloadAccessor.set(
                            session.payload,
                            f"{target_prefix}.{key}.{nested_key}",
                            nested_value,
                        )
            elif value is not None:
                PayloadAccessor.set(session.payload, f"{target_prefix}.{key}", value)

        # All Aadhaar cards are Indian; auto-fill country if not already set
        if not PayloadAccessor.get(session.payload, f"{target_prefix}.address.country"):
            PayloadAccessor.set(session.payload, f"{target_prefix}.address.country", "INDIA")

        # Normalise OCR-extracted state to UPPERCASE and expand abbreviations
        # so the stored value matches STATE_VALUES lookup keys and the picker values.
        state_path = f"{target_prefix}.address.state"
        raw_state = PayloadAccessor.get(session.payload, state_path)
        if raw_state:
            expanded = STATES.normalize(str(raw_state))   # maps "UP" → "UTTAR PRADESH" etc.
            normalised = expanded.strip().upper() if expanded else str(raw_state).strip().upper()
            PayloadAccessor.set(session.payload, state_path, normalised)

        district_path = f"{target_prefix}.address.district"
        raw_district = PayloadAccessor.get(session.payload, district_path)
        if raw_district:
            PayloadAccessor.set(
                session.payload,
                district_path,
                _normalise_delhi_district(str(raw_district)),
            )

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

        await self._log_extraction(session, image_bytes_list, parsed, None, True)
        return session

    async def _log_extraction(
        self,
        session: FormSession,
        image_bytes_list: list[bytes],
        parsed: dict,
        validation_error: str | None,
        aadhaar_valid: bool,
    ) -> None:
        if not self._analytics or session.analytics_session_id is None:
            return
        try:
            await self._analytics.log_extraction_event(
                session_id=session.analytics_session_id,
                telegram_user_id=session.telegram_user_id,
                person=session.current_confirming_person,
                image_count=len(image_bytes_list),
                raw_groq_response=parsed,
                validation_error=validation_error,
                aadhaar_valid=aadhaar_valid,
            )
        except Exception as exc:
            self._logger.warning("Failed to log extraction event: %s", exc)
