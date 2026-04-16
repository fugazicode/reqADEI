from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup

from infrastructure.analytics_store import AnalyticsStore
from infrastructure.razorpay_client import RazorpayClient, RazorpayError
from utils.qr_code import build_qr_png

LOGGER = logging.getLogger(__name__)

PAYMENT_STATUS_UNPAID = "unpaid"
PAYMENT_STATUS_PENDING = "awaiting_payment"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_EXPIRED = "expired"
PAYMENT_STATUS_CANCELLED = "cancelled"
PAYMENT_STATUS_ERROR = "error"


class PaymentService:
    def __init__(
        self,
        *,
        bot: Bot,
        analytics_store: AnalyticsStore,
        razorpay_client: RazorpayClient,
        amount_inr: int,
        currency: str,
        link_expire_minutes: int,
        description: str,
        pdf_dir: Path,
    ) -> None:
        self._bot = bot
        self._analytics = analytics_store
        self._razorpay = razorpay_client
        self._amount_inr = amount_inr
        self._currency = currency
        self._link_expire_minutes = link_expire_minutes
        self._description = description
        self._pdf_dir = pdf_dir
        self._pdf_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[int, asyncio.Lock] = {}

    async def close(self) -> None:
        await self._razorpay.close()

    async def handle_pdf_ready(
        self,
        *,
        session_id: int,
        telegram_user_id: int,
        request_number: str,
        pdf_bytes: bytes,
    ) -> None:
        async with self._lock_for(session_id):
            pdf_path = self._persist_pdf(session_id, request_number, pdf_bytes)
            await self._analytics.update_session(
                session_id,
                pdf_request_number=request_number,
                pdf_path=str(pdf_path),
                pdf_created_at=time.time(),
            )
            snapshot = await self._analytics.get_payment_snapshot(session_id)
            if snapshot and snapshot["payment_status"] == PAYMENT_STATUS_PAID:
                await self._send_pdf_if_ready(
                    session_id,
                    telegram_user_id,
                    Path(snapshot["pdf_path"] or pdf_path),
                    snapshot["pdf_request_number"] or request_number,
                )
                return

            link_url, is_new = await self._ensure_payment_link(
                session_id,
                telegram_user_id,
                request_number,
                snapshot,
            )
            if not link_url:
                await self._bot.send_message(
                    telegram_user_id,
                    "Payment link could not be generated right now. "
                    "Please try again with /payment in a few minutes.",
                )
                return

            await self._send_payment_instructions(telegram_user_id, link_url, is_new)

    async def resend_payment_link(self, telegram_user_id: int) -> None:
        session = await self._analytics.find_latest_payment_session_for_user(telegram_user_id)
        if not session:
            await self._bot.send_message(
                telegram_user_id,
                "No pending payment found for your account.",
            )
            return

        session_id = int(session["id"])
        async with self._lock_for(session_id):
            if session["payment_status"] == PAYMENT_STATUS_PAID:
                if session["pdf_sent_at"] is None and session["pdf_path"]:
                    await self._send_pdf_if_ready(
                        session_id,
                        telegram_user_id,
                        Path(session["pdf_path"]),
                        session["pdf_request_number"] or "verification",
                    )
                else:
                    await self._bot.send_message(
                        telegram_user_id,
                        "Payment already confirmed and the PDF has been sent.",
                    )
                return

            if not session["pdf_path"]:
                await self._bot.send_message(
                    telegram_user_id,
                    "Your PDF is still being prepared. Please wait for the payment link.",
                )
                return

            link_url, is_new = await self._ensure_payment_link(
                session_id,
                telegram_user_id,
                session["pdf_request_number"] or "verification",
                session,
            )
            if not link_url:
                await self._bot.send_message(
                    telegram_user_id,
                    "Payment link could not be generated right now. Please try again later.",
                )
                return

            await self._send_payment_instructions(telegram_user_id, link_url, is_new)

    async def handle_webhook(self, payload: dict) -> None:
        event_type = payload.get("event", "")
        link_entity = (
            payload.get("payload", {})
            .get("payment_link", {})
            .get("entity", {})
        )
        link_id = link_entity.get("id") if isinstance(link_entity, dict) else None
        if not link_id:
            LOGGER.warning("Webhook payload missing payment_link id")
            return

        session = await self._analytics.find_session_by_payment_link_id(link_id)
        if not session:
            LOGGER.warning("Webhook link_id not found in sessions: %s", link_id)
            return

        session_id = int(session["id"])
        telegram_user_id = int(session["telegram_user_id"])
        compact_event = _compact_event(payload)

        if event_type == "payment_link.paid":
            payment_entity = (
                payload.get("payload", {})
                .get("payment", {})
                .get("entity", {})
            )
            payment_id = None
            if isinstance(payment_entity, dict):
                payment_id = payment_entity.get("id")
            await self._analytics.update_session(
                session_id,
                payment_status=PAYMENT_STATUS_PAID,
                payment_paid_at=time.time(),
                payment_transaction_id=payment_id,
                payment_event_json=compact_event,
            )
            async with self._lock_for(session_id):
                if session["pdf_path"]:
                    await self._send_pdf_if_ready(
                        session_id,
                        telegram_user_id,
                        Path(session["pdf_path"]),
                        session["pdf_request_number"] or "verification",
                    )
                else:
                    await self._bot.send_message(
                        telegram_user_id,
                        "Payment received. Your PDF is still being prepared.",
                    )
            return

        if event_type in ("payment_link.expired", "payment_link.cancelled"):
            status = PAYMENT_STATUS_EXPIRED if event_type.endswith("expired") else PAYMENT_STATUS_CANCELLED
            await self._analytics.update_session(
                session_id,
                payment_status=status,
                payment_event_json=compact_event,
            )
            await self._bot.send_message(
                telegram_user_id,
                "Your payment link expired. Send /payment to get a new link.",
            )
            return

        LOGGER.info("Ignoring webhook event: %s", event_type)

    async def reconcile_paid_pdfs(self) -> None:
        rows = await self._analytics.list_paid_unsent_sessions()
        for row in rows:
            session_id = int(row["id"])
            telegram_user_id = int(row["telegram_user_id"])
            if not row["pdf_path"]:
                continue
            async with self._lock_for(session_id):
                await self._send_pdf_if_ready(
                    session_id,
                    telegram_user_id,
                    Path(row["pdf_path"]),
                    row["pdf_request_number"] or "verification",
                )

    async def poll_pending_payments(self) -> None:
        rows = await self._analytics.list_pending_payment_links()
        now = time.time()
        for row in rows:
            session_id = int(row["id"])
            telegram_user_id = int(row["telegram_user_id"])
            link_id = row["payment_link_id"]
            if not link_id:
                continue
            expiry = row["payment_link_expiry"] or 0
            if expiry and expiry <= now:
                await self._analytics.update_session(
                    session_id,
                    payment_status=PAYMENT_STATUS_EXPIRED,
                )
                await self._bot.send_message(
                    telegram_user_id,
                    "Your payment link expired. Send /payment to get a new link.",
                )
                continue

            try:
                data = await self._razorpay.get_payment_link(str(link_id))
            except RazorpayError as exc:
                LOGGER.warning("Payment link poll failed for %s: %s", link_id, exc)
                await self._analytics.update_session(
                    session_id,
                    payment_event_json=_compact_error(exc),
                )
                continue

            status = str(data.get("status", "")).lower()
            if status == "paid":
                paid_at = data.get("paid_at")
                paid_ts = float(paid_at) if isinstance(paid_at, (int, float)) else now
                payment_id = _extract_payment_id(data)
                await self._analytics.update_session(
                    session_id,
                    payment_status=PAYMENT_STATUS_PAID,
                    payment_paid_at=paid_ts,
                    payment_transaction_id=payment_id,
                    payment_event_json=_compact_data(data),
                )
                async with self._lock_for(session_id):
                    if row["pdf_path"]:
                        await self._send_pdf_if_ready(
                            session_id,
                            telegram_user_id,
                            Path(row["pdf_path"]),
                            row["pdf_request_number"] or "verification",
                        )
                    else:
                        await self._bot.send_message(
                            telegram_user_id,
                            "Payment received. Your PDF is still being prepared.",
                        )
                continue

            if status in ("expired", "cancelled"):
                new_status = PAYMENT_STATUS_EXPIRED if status == "expired" else PAYMENT_STATUS_CANCELLED
                await self._analytics.update_session(
                    session_id,
                    payment_status=new_status,
                    payment_event_json=_compact_data(data),
                )
                await self._bot.send_message(
                    telegram_user_id,
                    "Your payment link expired. Send /payment to get a new link.",
                )
                continue

    def _persist_pdf(self, session_id: int, request_number: str, pdf_bytes: bytes) -> Path:
        safe_request = _safe_token(request_number)
        filename = f"{session_id}_{safe_request}.pdf"
        path = self._pdf_dir / filename
        path.write_bytes(pdf_bytes)
        return path

    async def _ensure_payment_link(
        self,
        session_id: int,
        telegram_user_id: int,
        request_number: str,
        snapshot,
    ) -> tuple[str, bool]:
        now = time.time()
        if snapshot:
            expiry = snapshot["payment_link_expiry"] or 0
            if (
                snapshot["payment_status"] == PAYMENT_STATUS_PENDING
                and snapshot["payment_link_id"]
                and expiry > now
            ):
                url = snapshot["payment_link_short_url"] or snapshot["payment_link_url"]
                if url:
                    return str(url), False

        expire_by = int(now + self._link_expire_minutes * 60)
        reference_id = f"session_{session_id}"
        notes = {
            "telegram_user_id": str(telegram_user_id),
            "request_number": request_number,
        }
        try:
            data = await self._razorpay.create_payment_link(
                amount_paise=self._amount_inr * 100,
                currency=self._currency,
                reference_id=reference_id,
                description=self._description,
                expire_by=expire_by,
                notes=notes,
            )
        except RazorpayError as exc:
            LOGGER.warning("Payment link creation failed: %s", exc)
            await self._analytics.update_session(
                session_id,
                payment_status=PAYMENT_STATUS_ERROR,
                payment_event_json=_compact_error(exc),
            )
            return "", True

        link_id = data.get("id")
        short_url = _first_str(data, "short_url")
        link_url = _first_str(data, "url") or short_url
        if not link_id or not link_url:
            LOGGER.warning("Payment link response missing id or url: %s", data)
            await self._analytics.update_session(
                session_id,
                payment_status=PAYMENT_STATUS_ERROR,
                payment_event_json=_compact_data(data),
            )
            return "", True

        await self._analytics.increment_payment_attempts(session_id)
        await self._analytics.update_session(
            session_id,
            payment_status=PAYMENT_STATUS_PENDING,
            payment_provider="razorpay",
            payment_currency=self._currency,
            payment_amount=self._amount_inr,
            payment_link_id=link_id,
            payment_link_url=link_url,
            payment_link_short_url=short_url,
            payment_link_expiry=expire_by,
            payment_created_at=now,
            payment_reference=reference_id,
        )
        return link_url, True

    async def _send_payment_instructions(
        self, telegram_user_id: int, link_url: str, is_new: bool
    ) -> None:
        qr_bytes = build_qr_png(link_url)
        verb = "New" if is_new else "Existing"
        caption = (
            f"{verb} payment link ready.\n"
            f"Please pay INR {self._amount_inr} to receive your PDF.\n\n"
            f"Payment link: {link_url}\n\n"
            "After payment is confirmed, the PDF will be sent automatically.\n"
            "If the link expires, send /payment to get a new link."
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"Pay INR {self._amount_inr}", url=link_url)]
            ]
        )
        await self._bot.send_photo(
            telegram_user_id,
            BufferedInputFile(qr_bytes, "payment_qr.png"),
            caption=caption,
            reply_markup=keyboard,
        )

    async def _send_pdf_if_ready(
        self,
        session_id: int,
        telegram_user_id: int,
        pdf_path: Path,
        request_number: str,
    ) -> None:
        snapshot = await self._analytics.get_payment_snapshot(session_id)
        if snapshot and snapshot["pdf_sent_at"] is not None:
            return

        if not pdf_path.is_file():
            LOGGER.warning("PDF path missing for session %s: %s", session_id, pdf_path)
            await self._bot.send_message(
                telegram_user_id,
                "Payment received, but the PDF file is missing. Please contact support.",
            )
            return

        pdf_bytes = pdf_path.read_bytes()
        await self._bot.send_document(
            telegram_user_id,
            BufferedInputFile(pdf_bytes, "verification.pdf"),
            caption="Your tenant verification document.",
        )
        await self._bot.send_message(
            telegram_user_id,
            "Send /start to register another tenant.",
        )
        await self._analytics.update_session(
            session_id,
            pdf_sent_at=time.time(),
        )

    def _lock_for(self, session_id: int) -> asyncio.Lock:
        lock = self._locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[session_id] = lock
        return lock


def _safe_token(value: str) -> str:
    filtered = "".join(ch for ch in value if ch.isalnum() or ch in ("-", "_"))
    return filtered or "unknown"


def _compact_event(payload: dict) -> str:
    event = payload.get("event")
    payment_link = (
        payload.get("payload", {})
        .get("payment_link", {})
        .get("entity", {})
    )
    payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
    return json.dumps(
        {
            "event": event,
            "payment_link": payment_link,
            "payment": payment,
        }
    )


def _compact_error(exc: RazorpayError) -> str:
    payload = exc.payload if isinstance(exc.payload, dict) else {"error": str(exc.payload)}
    return json.dumps({"error": str(exc), "status": exc.status, "payload": payload})


def _compact_data(data: dict) -> str:
    return json.dumps({"data": data})


def _first_str(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _extract_payment_id(data: dict) -> str | None:
    payments = data.get("payments")
    if isinstance(payments, list):
        for entry in payments:
            if not isinstance(entry, dict):
                continue
            for key in ("payment_id", "id"):
                value = entry.get(key)
                if isinstance(value, str) and value:
                    return value

    payment = data.get("payment")
    if isinstance(payment, dict):
        for key in ("payment_id", "id"):
            value = payment.get(key)
            if isinstance(value, str) and value:
                return value
    return None
