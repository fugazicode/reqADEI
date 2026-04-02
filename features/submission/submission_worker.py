from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile
from playwright.async_api import Playwright, async_playwright

from features.submission.form_filler import FormFiller
from features.submission.portal_session import PortalSession
from shared.models.submission_input import SubmissionInput

LOGGER = logging.getLogger(__name__)


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
        self._queue: asyncio.Queue[SubmissionInput] = asyncio.Queue()

    async def enqueue(self, job: SubmissionInput) -> int:
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

    async def _process_job(self, job: SubmissionInput, pw: Playwright) -> None:
        # Flow: open session → fill form → submit → retrieve PDF → send document (no payment gate).
        session = PortalSession(self._username, self._password, pw, headless=False)
        try:
            page = await session.open()
            filler = FormFiller(page, job.payload)
            request_number = await filler.fill(job.image_bytes)
            if not request_number or request_number == "UNKNOWN":
                raise RuntimeError(
                    "Submission did not return a valid request number; skipping PDF retrieval."
                )
            pdf_bytes = await filler._retrieve_pdf(request_number)
            await self._bot.send_document(
                job.telegram_user_id,
                BufferedInputFile(pdf_bytes, "verification.pdf"),
                caption="Your tenant verification document.",
            )
        except Exception as exc:
            LOGGER.exception(
                "Submission failed for user %d: %s",
                job.telegram_user_id,
                exc,
            )
            await self._bot.send_message(
                job.telegram_user_id,
                "❌ Submission failed. Please try again or contact support.",
            )
        finally:
            await session.close()
