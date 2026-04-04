from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.types import BufferedInputFile
from playwright.async_api import Playwright, async_playwright

from features.submission.form_filler import FormFiller
from features.submission.portal_session import PortalSession
from infrastructure.submission_snapshot import save_snapshot
from shared.models.submission_input import SubmissionInput

LOGGER = logging.getLogger(__name__)


async def execute_playwright_submission(
    job: SubmissionInput,
    pw: Playwright,
    *,
    portal_username: str,
    portal_password: str,
    headless: bool = False,
) -> tuple[str, bytes]:
    """Run portal login, form fill, submit, and PDF download. No Telegram."""
    session = PortalSession(
        portal_username, portal_password, pw, headless=headless
    )
    try:
        page = await session.open()
        filler = FormFiller(page, job.payload)
        request_number = await filler.fill(job.image_bytes)
        if not request_number or request_number == "UNKNOWN":
            raise RuntimeError(
                "Submission did not return a valid request number; skipping PDF retrieval."
            )
        pdf_bytes = await filler._retrieve_pdf(request_number)
        return request_number, pdf_bytes
    finally:
        await session.close()


class SubmissionWorker:
    def __init__(
        self,
        *,
        bot: Bot,
        portal_username: str,
        portal_password: str,
        snapshot_dir: Path | None = None,
    ) -> None:
        self._bot = bot
        self._username = portal_username
        self._password = portal_password
        self._snapshot_dir = snapshot_dir
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
        if self._snapshot_dir is not None:
            snap_dir = self._snapshot_dir / str(job.telegram_user_id)
            await asyncio.to_thread(save_snapshot, snap_dir, job)
            LOGGER.info("Snapshot saved to %s", snap_dir)
        try:
            request_number, pdf_bytes = await execute_playwright_submission(
                job,
                pw,
                portal_username=self._username,
                portal_password=self._password,
                headless=False,
            )
            await self._bot.send_document(
                job.telegram_user_id,
                BufferedInputFile(pdf_bytes, "verification.pdf"),
                caption="Your tenant verification document.",
            )
            await self._bot.send_message(
                job.telegram_user_id,
                "Send /start to register another tenant.",
            )
        except Exception as exc:
            LOGGER.exception(
                "Submission failed for user %d: %s",
                job.telegram_user_id,
                exc,
            )
            await self._bot.send_message(
                job.telegram_user_id,
                "❌ Submission failed. Please try again or contact support.\n\n"
                "Send /start to register another tenant.",
            )
