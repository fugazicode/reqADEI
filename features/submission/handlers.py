from aiogram import Router, F
from aiogram.types import PreCheckoutQuery, Message, SuccessfulPayment, LabeledPrice, BufferedInputFile
from aiogram.fsm.context import FSMContext
import json
import time
from datetime import datetime
from features.submission.submission_worker import SubmissionWorker
from shared.config import Settings
from infrastructure.refund_ledger import RefundLedger
from features.submission.states import SubmissionStates

router = Router()

@router.pre_checkout_query()
async def handle_pre_checkout(
    query: PreCheckoutQuery,
    submission_worker: SubmissionWorker,
) -> None:
    try:
        payload_dict = json.loads(query.invoice_payload)
        user_id = payload_dict["user_id"]
    except Exception:
        await query.answer(ok=False, error_message="Invalid payment data.")
        return
    if user_id not in submission_worker._pending_deliveries:
        await query.answer(ok=False, error_message="Session expired.")
        return
    await query.answer(ok=True)

@router.message(SubmissionStates.AWAITING_PAYMENT, F.successful_payment.as_("payment"))
async def handle_successful_payment(
    message: Message,
    payment: SuccessfulPayment,
    state: FSMContext,
    bot,
    submission_worker: SubmissionWorker,
    refund_ledger: RefundLedger,
) -> None:
    user_id = message.from_user.id
    clean_bytes = submission_worker._pending_deliveries.pop(user_id, None)
    if clean_bytes is not None:
        await bot.send_document(user_id, BufferedInputFile(clean_bytes, "verification.pdf"), caption="Your tenant verification document.")
    else:
        await bot.send_message(user_id, "Sorry, your document was lost. Please contact support.")
    try:
        payload = json.loads(payment.invoice_payload)
        request_number = payload["request_number"]
    except Exception:
        request_number = "UNKNOWN"
    from infrastructure.refund_ledger import RefundEntry
    entry = RefundEntry(
        charge_id=payment.telegram_payment_charge_id,
        user_id=user_id,
        request_number=request_number,
        paid_at=time.time(),
        status="eligible"
    )
    refund_ledger.add(entry)
    task = submission_worker._cleanup_tasks.pop(user_id, None)
    if task:
        task.cancel()
    await state.set_state(SubmissionStates.COMPLETE)

@router.message(F.text == "/test_invoice")
async def test_invoice(
    message: Message,
    state: FSMContext,
    bot: Bot,
    settings: Settings,
    submission_worker: SubmissionWorker,
) -> None:
    if message.from_user.id != settings.admin_telegram_id:
        return

    # ── TEST CONSTANT ────────────────────────────────────────────────────────
    # Hardcoded for isolated payment testing. When moving to full flow,
    # this will be replaced by the request_number from _submit_and_get_result()
    TEST_REQUEST_NUMBER = "816726116865"
    # ────────────────────────────────────────────────────────────────────────

    await message.answer("Starting test: retrieving real PDF from portal...")

    from playwright.async_api import async_playwright
    from features.submission.portal_session import PortalSession
    from features.submission.form_filler import FormFiller
    from tests.sample_payload import make_sample_payload
    from utils.watermark import apply_watermark

    try:
        async with async_playwright() as pw:
            session = PortalSession(
                settings.portal_username,
                settings.portal_password,
                pw,
                headless=True,
            )
            try:
                page = await session.open()
                payload = make_sample_payload()
                filler = FormFiller(page, payload)

                await message.answer("Portal login successful. Retrieving PDF...")
                clean_bytes = await filler._retrieve_pdf(TEST_REQUEST_NUMBER)

                if not clean_bytes or clean_bytes[:4] != b"%PDF" or len(clean_bytes) < 1000:
                    await message.answer(
                        f"PDF retrieval failed — got {len(clean_bytes)} bytes. Aborting test."
                    )
                    return

                await message.answer(
                    f"PDF retrieved successfully ({len(clean_bytes)} bytes). Applying watermark..."
                )
                watermarked_bytes = apply_watermark(clean_bytes)
                await message.answer(
                    f"Watermark applied ({len(watermarked_bytes)} bytes). Sending preview..."
                )

                await bot.send_document(
                    chat_id=message.from_user.id,
                    document=BufferedInputFile(watermarked_bytes, "preview.pdf"),
                    caption="Preview of your verification document. Pay to receive the clean copy.",
                )

            finally:
                await session.close()

    except Exception as exc:
        await message.answer(f"Portal session failed: {exc}")
        return

    user_id = message.from_user.id
    submission_worker._pending_deliveries[user_id] = clean_bytes

    payload_str = json.dumps({
        "user_id": user_id,
        "request_number": TEST_REQUEST_NUMBER,
        "timestamp": time.time(),
    })

    await bot.send_invoice(
        chat_id=user_id,
        title="Tenant Verification Document",
        description="Official Delhi Police CCTNS tenant verification form.",
        payload=payload_str,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Verification Document", amount=1)],
    )
    await state.set_state(SubmissionStates.AWAITING_PAYMENT)
    await message.answer("Invoice sent. Waiting for payment...")

@router.message(F.text == "/refund")
async def user_refund(
    message: Message,
    refund_ledger: RefundLedger,
    settings: Settings,
    bot,
) -> None:
    user_id = message.from_user.id
    entry = refund_ledger.get_latest_eligible(user_id)
    if entry is None:
        await message.answer("No eligible payment found for refund.")
        return
    if entry.status == "requested":
        await message.answer("Your refund request is already under review.")
        return
    if time.time() - entry.paid_at > 7 * 86400:
        await message.answer("Refund window closed (7 days have passed).")
        return
    refund_ledger.update_status(entry.charge_id, "requested")
    await bot.send_message(settings.admin_telegram_id, f"⚠️ Refund request\nUser: {user_id}\nCharge: {entry.charge_id}\nRequest: {entry.request_number}\nPaid at: {datetime.fromtimestamp(entry.paid_at)}\n\n/approve_refund {entry.charge_id}\n/reject_refund {entry.charge_id} <reason>")
    await message.answer("Refund request submitted. You will be notified when reviewed.")

@router.message(F.text.startswith("/approve_refund"))
async def approve_refund(message: Message, bot, refund_ledger: RefundLedger, settings: Settings) -> None:
    if message.from_user.id != settings.admin_telegram_id:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /approve_refund <charge_id>")
        return
    charge_id = parts[1].strip()
    entry = refund_ledger.get_by_charge_id(charge_id)
    if not entry:
        await message.answer("Charge ID not found.")
        return
    result = await bot.refund_star_payment(user_id=entry.user_id, telegram_payment_charge_id=charge_id)
    if result is True:
        refund_ledger.update_status(charge_id, "approved")
        await bot.send_message(entry.user_id, "Your refund has been approved.")
        await message.answer("Approved.")
    else:
        await message.answer("Refund call returned False — check Telegram logs.")

@router.message(F.text.startswith("/reject_refund"))
async def reject_refund(message: Message, bot, refund_ledger: RefundLedger, settings: Settings) -> None:
    if message.from_user.id != settings.admin_telegram_id:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Usage: /reject_refund <charge_id> <reason>")
        return
    charge_id = parts[1]
    reason = parts[2] if len(parts) > 2 else ""
    entry = refund_ledger.get_by_charge_id(charge_id)
    if not entry:
        await message.answer("Charge ID not found.")
        return
    refund_ledger.update_status(charge_id, "rejected", reason=reason)
    await bot.send_message(entry.user_id, f"Your refund was rejected. Reason: {reason}")
    await message.answer("Rejected.")
