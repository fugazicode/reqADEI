from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from core.engine import PipelineEngine
from core.pipeline_stages import ImageParsingStage
from infrastructure.fsm_logger import AnalyticsMiddleware
from features.address_collection.handlers import router as address_collection_router
from features.data_verification.handlers import router as data_verification_router
from features.identity_collection.handlers import router as identity_collection_router
from features.submission.submission_worker import SubmissionWorker
from infrastructure.analytics_store import AnalyticsStore
from infrastructure.groq_parser import GroqParser
from infrastructure.payment_service import PaymentService
# from infrastructure.payment_webhook import PaymentWebhookServer
from infrastructure.razorpay_client import RazorpayClient
from infrastructure.session_store import SessionStore
from shared.config import load_settings
from shared.logger import configure_logger
from utils.station_lookup import StationLookup
from features.submission.handlers import router as submission_router

LOGGER = logging.getLogger(__name__)

root_router = Router(name="root")


@root_router.message(StateFilter("*"), Command("cancel"))
async def cancel_root(message: Message, state: FSMContext, session_store: SessionStore) -> None:
    if not message.from_user:
        return
    await state.clear()
    session_store.delete(message.from_user.id)
    await message.answer("Form cancelled. Send /start to begin again.")


def _build_pipeline(
    groq_parser: GroqParser,
    bot: Bot,
    analytics_store: AnalyticsStore,
    station_lookup: StationLookup,
) -> PipelineEngine:
    return PipelineEngine([ImageParsingStage(groq_parser, bot, station_lookup, analytics_store)])


async def _session_cleanup_loop(session_store: SessionStore) -> None:
    while True:
        await asyncio.sleep(3600)
        session_store.cleanup_expired()


async def _payment_reconcile_loop(payment_service: PaymentService) -> None:
    while True:
        await asyncio.sleep(300)
        try:
            await payment_service.reconcile_paid_pdfs()
        except Exception:
            LOGGER.exception("Payment reconciliation failed")


async def _payment_poll_loop(payment_service: PaymentService, interval_s: int) -> None:
    while True:
        await asyncio.sleep(interval_s)
        try:
            await payment_service.poll_pending_payments()
        except Exception:
            LOGGER.exception("Payment polling failed")


async def run() -> None:
    config = load_settings()
    configure_logger(config.log_level)

    base_dir = Path(__file__).resolve().parent

    bot = Bot(token=config.bot_token)
    dp = Dispatcher()

    session_store = SessionStore()

    groq_parser = GroqParser(
        api_key=config.groq_api_key,
        model=config.groq_model,
        vision_model=config.groq_vision_model,
        prompts_dir=base_dir / "prompts",
    )

    station_lookup = StationLookup(
        stations_file=base_dir / "data" / "delhi_police_stations.json",
        national_file=base_dir / "data" / "national_police_stations.json",
        unified_file=base_dir / "data" / "police_stations.json",
    )

    analytics_store = AnalyticsStore(base_dir / "data" / "analytics.db")

    razorpay_client = RazorpayClient(
        config.razorpay_key_id,
        config.razorpay_key_secret,
    )
    payment_service = PaymentService(
        bot=bot,
        analytics_store=analytics_store,
        razorpay_client=razorpay_client,
        amount_inr=config.payment_amount_inr,
        currency=config.payment_currency,
        link_expire_minutes=config.payment_link_expire_minutes,
        description=config.payment_description,
        pdf_dir=config.payment_pdf_dir,
    )
    # payment_webhook = PaymentWebhookServer(
    #     payment_service,
    #     secret=config.razorpay_webhook_secret,
    #     host=config.payment_webhook_host,
    #     port=config.payment_webhook_port,
    #     path=config.payment_webhook_path,
    # )

    pipeline = _build_pipeline(groq_parser, bot, analytics_store, station_lookup)

    submission_worker = SubmissionWorker(
        bot=bot,
        portal_username=config.portal_username,
        portal_password=config.portal_password,
        snapshot_dir=config.snapshot_dir,
        analytics_store=analytics_store,
        payment_service=payment_service,
    )

    # Inject dependencies via dispatcher context
    dp["session_store"] = session_store
    dp["groq_parser"] = groq_parser
    dp["station_lookup"] = station_lookup
    dp["pipeline"] = pipeline
    dp["analytics_store"] = analytics_store
    dp["bot"] = bot
    dp["submission_worker"] = submission_worker
    dp["payment_service"] = payment_service

    analytics_mw = AnalyticsMiddleware(analytics_store, session_store)
    dp.message.middleware(analytics_mw)
    dp.callback_query.middleware(analytics_mw)

    dp.include_router(root_router)
    dp.include_router(identity_collection_router)
    dp.include_router(data_verification_router)
    dp.include_router(address_collection_router)
    dp.include_router(submission_router)

    async def on_startup() -> None:
        await analytics_store.init()
        asyncio.create_task(_session_cleanup_loop(session_store))
        asyncio.create_task(submission_worker.start())
        asyncio.create_task(_payment_reconcile_loop(payment_service))
        asyncio.create_task(_payment_poll_loop(payment_service, config.payment_poll_interval_s))
        # await payment_webhook.start()

    async def on_shutdown() -> None:
        # await payment_webhook.stop()
        await payment_service.close()
        await analytics_store.close()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(run())
