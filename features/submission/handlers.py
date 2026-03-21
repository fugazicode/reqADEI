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
async def test_invoice(message: Message, bot, settings: Settings) -> None:
    if message.from_user.id != settings.admin_telegram_id:
        return
    payload = json.dumps({"user_id": message.from_user.id, "request_number": "TEST-0000", "timestamp": time.time()})
        submission_worker._pending_deliveries[message.from_user.id] = b"TEST_DOCUMENT_PLACEHOLDER"  # ADD THIS
    await bot.send_invoice(
        chat_id=message.from_user.id,
        title="Test Invoice",
        description="Test Stars payment.",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("Test", 1)],
    )

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
