from __future__ import annotations

import io

from aiogram import Bot

from core.stage_interface import PipelineStage
from features.data_verification.confirmation_flow import ConfirmationFlow
from infrastructure.groq_parser import GroqParser
from infrastructure.vision_client import VisionClient
from shared.models.session import FormSession
from utils.payload_accessor import PayloadAccessor


class ImageExtractionStage(PipelineStage):
    name = "extract_images"

    def __init__(self, vision_client: VisionClient, bot: Bot) -> None:
        self._vision_client = vision_client
        self._bot = bot

    async def execute(self, session: FormSession) -> FormSession:
        session.raw_ocr_text = ""
        file_ids = (
            session.owner_image_file_ids
            if session.current_confirming_person == "owner"
            else session.tenant_image_file_ids
        )

        extracted_texts: list[str] = []
        for file_id in file_ids:
            buffer = io.BytesIO()
            await self._bot.download(file_id, destination=buffer)
            image_bytes = buffer.getvalue()
            extracted_texts.append(await self._vision_client.extract_text(image_bytes))

        session.raw_ocr_text = "\n---\n".join(filter(None, extracted_texts))
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

        ConfirmationFlow.build_queue(session)
        return session
