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


class SubmissionWorker:
    def __init__(
        self,
        *,
        bot: Bot,
        portal_username: str,
        portal_password: str,
    ) -> None:
        self._bot = bot
        self._username = portal_username
        self._password = portal_password
        self._queue: asyncio.Queue[SubmissionJob] = asyncio.Queue()

    async def enqueue(self, job: SubmissionJob) -> int:
        await self._queue.put(job)
        return self._queue.qsize()

    async def start(self) -> None:
        LOGGER.info("Submission worker started")
        async with async_playwright() as pw:
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

    async def _process_job(self, job: SubmissionJob, pw: Playwright) -> None:
        session = PortalSession(self._username, self._password, pw, headless=True)
        try:
            page = await session.open()
            filler = FormFiller(page, job.payload)
            request_number = await filler.fill(job.image_bytes)
            pdf_bytes = await filler._retrieve_pdf(request_number)
            await self._bot.send_document(
                job.telegram_user_id,
                BufferedInputFile(pdf_bytes, "verification.pdf"),
                caption="Your tenant verification document.",
            )
        except Exception as exc:
            await self._bot.send_message(
                job.telegram_user_id,
                f"❌ Submission failed: {exc}",
            )
        finally:
            await session.close()
