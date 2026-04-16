from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    groq_api_key: str
    groq_model: str
    groq_vision_model: str
    log_level: str
    portal_username: str
    portal_password: str
    admin_telegram_id: int
    snapshot_dir: Path | None = field(default=None)
    razorpay_key_id: str = field(default="")
    razorpay_key_secret: str = field(default="")
    razorpay_webhook_secret: str = field(default="")
    payment_amount_inr: int = field(default=30)
    payment_currency: str = field(default="INR")
    payment_link_expire_minutes: int = field(default=60)
    payment_description: str = field(default="Tenant verification PDF")
    payment_pdf_dir: Path = field(default_factory=lambda: Path("data") / "pdfs")
    payment_webhook_host: str = field(default="0.0.0.0")
    payment_webhook_port: int = field(default=8080)
    payment_webhook_path: str = field(default="/webhooks/razorpay")
    payment_poll_interval_s: int = field(default=60)


def load_settings() -> Settings:
    load_dotenv()
    admin_telegram_id_str = os.getenv("ADMIN_TELEGRAM_ID")
    if not admin_telegram_id_str or not admin_telegram_id_str.isdigit():
        raise ValueError("ADMIN_TELEGRAM_ID must be set in .env")
    admin_telegram_id = int(admin_telegram_id_str)

    raw_snapshot_dir = os.getenv("SUBMISSION_SNAPSHOT_DIR", "").strip()
    snapshot_dir = Path(raw_snapshot_dir) if raw_snapshot_dir else None

    razorpay_key_id = os.getenv("RAZORPAY_KEY_ID", "").strip()
    razorpay_key_secret = os.getenv("RAZORPAY_KEY_SECRET", "").strip()
    razorpay_webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
    if not razorpay_key_id or not razorpay_key_secret:
        raise ValueError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set in .env")

    payment_amount_inr = int(os.getenv("PAYMENT_AMOUNT_INR", "30"))
    payment_currency = os.getenv("PAYMENT_CURRENCY", "INR").strip() or "INR"
    payment_link_expire_minutes = int(os.getenv("PAYMENT_LINK_EXPIRE_MINUTES", "60"))
    payment_description = os.getenv("PAYMENT_DESCRIPTION", "Tenant verification PDF").strip()
    payment_pdf_dir = Path(os.getenv("PAYMENT_PDF_DIR", "data/pdfs")).resolve()
    payment_webhook_host = os.getenv("PAYMENT_WEBHOOK_HOST", "0.0.0.0").strip() or "0.0.0.0"
    payment_webhook_port = int(os.getenv("PAYMENT_WEBHOOK_PORT", "8080"))
    payment_webhook_path = os.getenv("PAYMENT_WEBHOOK_PATH", "/webhooks/razorpay").strip()
    payment_poll_interval_s = int(os.getenv("PAYMENT_POLL_INTERVAL_S", "60"))

    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        groq_vision_model=os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        portal_username=os.getenv("PORTAL_USERNAME", ""),
        portal_password=os.getenv("PORTAL_PASSWORD", ""),
        admin_telegram_id=admin_telegram_id,
        snapshot_dir=snapshot_dir,
        razorpay_key_id=razorpay_key_id,
        razorpay_key_secret=razorpay_key_secret,
        razorpay_webhook_secret=razorpay_webhook_secret,
        payment_amount_inr=payment_amount_inr,
        payment_currency=payment_currency,
        payment_link_expire_minutes=payment_link_expire_minutes,
        payment_description=payment_description,
        payment_pdf_dir=payment_pdf_dir,
        payment_webhook_host=payment_webhook_host,
        payment_webhook_port=payment_webhook_port,
        payment_webhook_path=payment_webhook_path,
        payment_poll_interval_s=payment_poll_interval_s,
    )
