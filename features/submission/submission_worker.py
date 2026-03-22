from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from playwright.async_api import Playwright, async_playwright

from features.submission.form_filler import FormFiller
from features.submission.portal_session import PortalSession
from shared.models.form_payload import FormPayload

LOGGER = logging.getLogger(__name__)


@dataclass
class SubmissionJob:
    telegram_user_id: int
    payload: FormPayload
    image_bytes: bytes


import json
import time
from aiogram.types import BufferedInputFile, LabeledPrice, Message, SuccessfulPayment
from aiogram.fsm.storage.base import StorageKey
from shared.config import Settings
from infrastructure.refund_ledger import RefundLedger, RefundEntry
from utils.watermark import apply_watermark
from features.submission.states import SubmissionStates

class SubmissionWorker:
    def __init__(
        self,
        *,
        bot: Bot,
        portal_username: str,
        portal_password: str,
        settings: Settings,
        refund_ledger: RefundLedger,
        storage,
    ) -> None:
        self._bot = bot
        self._username = portal_username
        self._password = portal_password
        self._settings = settings
        self._refund_ledger = refund_ledger
        self._storage = storage
        self._queue: asyncio.Queue[SubmissionJob] = asyncio.Queue()
        self._pending_deliveries: dict[int, bytes] = {}
        self._cleanup_tasks: dict[int, asyncio.Task] = {}
        self._bot_id: int = 0

    async def enqueue(self, job: SubmissionJob) -> int:
        await self._queue.put(job)
        return self._queue.qsize()

    async def start(self) -> None:
        LOGGER.info("Submission worker started")
        self._bot_id = 0
        async with async_playwright() as pw:
            bot_info = await self._bot.get_me()
            self._bot_id = bot_info.id
            while True:
                job = await self._queue.get()
                try:
                    await self._process_job(job, pw)
                except Exception:
                    LOGGER.exception(
                        "Unhandled error processing submission for user %d",
                        job.telegram_user_id,
                    )
                finally:
                    self._queue.task_done()

    async def _set_fsm_state(self, user_id: int, state) -> None:
        key = StorageKey(bot_id=self._bot_id, chat_id=user_id, user_id=user_id)
        await self._storage.set_state(key=key, state=state.state if state else None)

    async def _payment_timeout(self, user_id: int) -> None:
        await asyncio.sleep(1800)
        if user_id in self._pending_deliveries:
            del self._pending_deliveries[user_id]
            await self._bot.send_message(
                user_id, "Payment window expired. Send /start to begin again."
            )
            await self._set_fsm_state(user_id, None)
        self._cleanup_tasks.pop(user_id, None)

    async def _process_job(self, job: SubmissionJob, pw: Playwright) -> None:
        session = PortalSession(self._username, self._password, pw)
        try:
            page = await session.open()
            filler = FormFiller(page, job.payload)
            request_number = await filler.fill(job.image_bytes)
            clean_bytes = await filler._retrieve_pdf(request_number)
            watermarked_bytes = apply_watermark(clean_bytes)
            await self._bot.send_document(
                job.telegram_user_id,
                BufferedInputFile(watermarked_bytes, "preview.pdf"),
                caption="Preview of your verification document. Pay to receive the clean copy."
            )
            if self._settings.payment_test_mode:
                await self._bot.send_document(
                    job.telegram_user_id,
                    BufferedInputFile(clean_bytes, "verification.pdf"),
                    caption="Test mode — clean document delivered without payment."
                )
                entry = RefundEntry(
                    charge_id=f"TEST-{job.telegram_user_id}-{int(time.time())}",
                    user_id=job.telegram_user_id,
                    request_number=request_number,
                    paid_at=time.time(),
                    status="eligible",
                    test_mode=True
                )
                self._refund_ledger.add(entry)
                await self._set_fsm_state(job.telegram_user_id, SubmissionStates.COMPLETE)
            else:
                invoice_payload = json.dumps({
                    "user_id": job.telegram_user_id,
                    "request_number": request_number,
                    "timestamp": time.time(),
                })
                await self._bot.send_invoice(
                    chat_id=job.telegram_user_id,
                    title="Tenant Verification Document",
                    description="Official Delhi Police CCTNS tenant verification form.",
                    payload=invoice_payload,
                    provider_token="",
                    currency="XTR",
                    prices=[LabeledPrice(label="Verification Document", amount=self._settings.stars_price)],
                )
                self._pending_deliveries[job.telegram_user_id] = clean_bytes
                task = self._cleanup_tasks.pop(job.telegram_user_id, None)
                if task:
                    task.cancel()
                task = asyncio.create_task(self._payment_timeout(job.telegram_user_id))
                self._cleanup_tasks[job.telegram_user_id] = task
                await self._set_fsm_state(job.telegram_user_id, SubmissionStates.AWAITING_PAYMENT)
        except Exception as exc:
            await self._bot.send_message(
                job.telegram_user_id,
                f"❌ Submission failed: {exc}",
            )
        finally:
            await session.close()
