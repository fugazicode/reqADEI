from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.types import Message

from core.engine import PipelineEngine
from core.pipeline_stages import IdParsingStage, ImageExtractionStage
from features.data_verification.handlers import router as data_verification_router
from features.extras_collection.handlers import router as extras_collection_router
from features.identity_collection.handlers import router as identity_collection_router
from features.identity_collection.keyboards import done_upload_keyboard
from features.identity_collection.states import IdentityCollectionStates
from infrastructure.groq_parser import GroqParser
from infrastructure.session_store import SessionStore
from infrastructure.vision_client import (
    VisionClient,
    VisionConfigurationError,
    VisionServiceUnavailable,
)
from shared.config import load_settings
from shared.logger import configure_logger
from shared.models.session import FormSession
from utils.station_lookup import StationLookup


LOGGER = logging.getLogger(__name__)


root_router = Router(name="root")


@root_router.message(StateFilter("*"), F.text == "/start")
async def start_root(message: Message, state: FSMContext, session_store: SessionStore) -> None:
    if not message.from_user:
        return

    await state.clear()
    await session_store.delete(message.from_user.id)

    session = FormSession(telegram_user_id=message.from_user.id)
    await session_store.save(session)

    await state.set_state(IdentityCollectionStates.OWNER_UPLOAD)
    response = await message.answer(
        "Upload owner ID images, then tap Done.",
        reply_markup=done_upload_keyboard(),
    )
    session.upload_status_message_id = response.message_id
    await session_store.save(session)


@root_router.message(StateFilter("*"), F.text == "/cancel")
async def cancel_root(message: Message, state: FSMContext, session_store: SessionStore) -> None:
    if not message.from_user:
        return

    await state.clear()
    await session_store.delete(message.from_user.id)
    await message.answer("Form cancelled. Send /start to begin again.")


def _build_pipeline(vision_client: VisionClient, groq_parser: GroqParser, bot: Bot) -> PipelineEngine:
    return PipelineEngine(
        [
            ImageExtractionStage(vision_client, bot),
            IdParsingStage(groq_parser),
        ]
    )


async def _preflight_ocr(vision_client: VisionClient) -> None:
    try:
        await vision_client.validate_api_key()
    except VisionServiceUnavailable as exc:
        LOGGER.warning("OCR preflight skipped due to service/network issue: %s", exc)
    except VisionConfigurationError:
        raise


async def run() -> None:
    config = load_settings()
    configure_logger(config.log_level)

    bot = Bot(token=config.bot_token)
    dp = Dispatcher()

    session_store = SessionStore()
    vision_client = VisionClient(config.ocr_space_api_key)
    await _preflight_ocr(vision_client)

    base_dir = Path(__file__).resolve().parent
    groq_parser = GroqParser(
        api_key=config.groq_api_key,
        model=config.groq_model,
        prompts_dir=base_dir / "prompts",
    )
    station_lookup = StationLookup(base_dir / "data" / "police_stations.json")

    owner_engine = _build_pipeline(vision_client, groq_parser, bot)
    tenant_engine = _build_pipeline(vision_client, groq_parser, bot)

    dp["session_store"] = session_store
    dp["owner_engine"] = owner_engine
    dp["tenant_engine"] = tenant_engine
    dp["groq_parser"] = groq_parser
    dp["station_lookup"] = station_lookup
    dp["bot"] = bot

    dp.include_router(root_router)
    dp.include_router(identity_collection_router)
    dp.include_router(data_verification_router)
    dp.include_router(extras_collection_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
