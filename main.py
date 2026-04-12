from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from core.engine import PipelineEngine
from core.pipeline_stages import ImageParsingStage
from infrastructure.fsm_logger import AnalyticsMiddleware
from infrastructure.heartbeat import heartbeat_loop, notify_recovery
from features.address_collection.handlers import router as address_collection_router
from features.data_verification.handlers import router as data_verification_router
from features.identity_collection.handlers import router as identity_collection_router
from features.submission.submission_worker import SubmissionWorker
from infrastructure.analytics_store import AnalyticsStore
from infrastructure.groq_parser import GroqParser
from infrastructure.session_store import SessionStore
from shared.config import load_settings
from shared.logger import configure_logger
from utils.station_lookup import StationLookup

LOGGER = logging.getLogger(__name__)

root_router = Router(name="root")


@root_router.message(StateFilter("*"), Command("cancel"))
async def cancel_root(message: Message, state: FSMContext, session_store: SessionStore) -> None:
    if not message.from_user:
        return
    await state.clear()
    session_store.delete(message.from_user.id)
    await message.answer("Form cancelled. Send /start to begin again.")


def _build_pipeline(groq_parser: GroqParser, bot: Bot, analytics_store: AnalyticsStore) -> PipelineEngine:
    return PipelineEngine([ImageParsingStage(groq_parser, bot, analytics_store)])


async def _session_cleanup_loop(session_store: SessionStore) -> None:
    while True:
        await asyncio.sleep(3600)
        session_store.cleanup_expired()


async def run() -> None:
    config = load_settings()
    configure_logger(config.log_level)

    missing = [
        name
        for name, val in [
            ("WORKER_URL", config.worker_url),
            ("WORKER_SECRET", config.worker_secret),
            ("TELEGRAM_WEBHOOK_SECRET", config.telegram_webhook_secret),
            ("TUNNEL_URL", config.tunnel_url),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            f"Missing required env vars for webhook mode: {', '.join(missing)}. "
            "Set them in .env before starting."
        )

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
    )

    analytics_store = AnalyticsStore(base_dir / "data" / "analytics.db")

    pipeline = _build_pipeline(groq_parser, bot, analytics_store)

    submission_worker = SubmissionWorker(
        bot=bot,
        portal_username=config.portal_username,
        portal_password=config.portal_password,
        snapshot_dir=config.snapshot_dir,
        analytics_store=analytics_store,
    )

    dp["session_store"] = session_store
    dp["groq_parser"] = groq_parser
    dp["station_lookup"] = station_lookup
    dp["pipeline"] = pipeline
    dp["analytics_store"] = analytics_store
    dp["bot"] = bot
    dp["submission_worker"] = submission_worker

    analytics_mw = AnalyticsMiddleware(analytics_store, session_store)
    dp.message.middleware(analytics_mw)
    dp.callback_query.middleware(analytics_mw)

    dp.include_router(root_router)
    dp.include_router(identity_collection_router)
    dp.include_router(data_verification_router)
    dp.include_router(address_collection_router)

    async def on_startup() -> None:
        await analytics_store.init()

        await bot.set_webhook(
            url=f"{config.worker_url}/webhook",
            secret_token=config.telegram_webhook_secret,
            drop_pending_updates=True,
        )
        LOGGER.info("Webhook set to %s/webhook", config.worker_url)
        LOGGER.info(
            "Tunnel URL (must match wrangler LOCAL_BOT_URL): %s", config.tunnel_url
        )

        await notify_recovery(config.worker_url, config.worker_secret, bot)

        asyncio.create_task(_session_cleanup_loop(session_store))
        asyncio.create_task(submission_worker.start())
        asyncio.create_task(
            heartbeat_loop(config.worker_url, config.worker_secret, interval=30)
        )

    async def on_shutdown() -> None:
        await analytics_store.close()
        await bot.delete_webhook(drop_pending_updates=False)
        LOGGER.info("Webhook deleted on shutdown")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=config.telegram_webhook_secret,
    ).register(app, path=config.local_webhook_path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.local_webhook_port)
    await site.start()

    LOGGER.info(
        "Webhook server listening on 0.0.0.0:%d%s",
        config.local_webhook_port,
        config.local_webhook_path,
    )

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(run())
