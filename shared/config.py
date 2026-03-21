from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    ocr_space_api_key: str
    groq_api_key: str
    groq_model: str
    log_level: str
    portal_username: str
    portal_password: str

    stars_price: int
    payment_test_mode: bool
    admin_telegram_id: int



def load_settings() -> Settings:
    load_dotenv()
    stars_price = int(os.getenv("STARS_PRICE", 35))
    payment_test_mode = os.getenv("PAYMENT_TEST_MODE", "false").lower() == "true"
    admin_telegram_id_str = os.getenv("ADMIN_TELEGRAM_ID")
    if not admin_telegram_id_str or not admin_telegram_id_str.isdigit():
        raise ValueError("ADMIN_TELEGRAM_ID must be set in .env")
    admin_telegram_id = int(admin_telegram_id_str)

    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        ocr_space_api_key=os.getenv("OCR_SPACE_API_KEY", ""),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        portal_username=os.getenv("PORTAL_USERNAME", ""),
        portal_password=os.getenv("PORTAL_PASSWORD", ""),
        stars_price=stars_price,
        payment_test_mode=payment_test_mode,
        admin_telegram_id=admin_telegram_id,
    )
