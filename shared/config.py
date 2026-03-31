from __future__ import annotations

from dataclasses import dataclass
import os

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


def load_settings() -> Settings:
    load_dotenv()
    admin_telegram_id_str = os.getenv("ADMIN_TELEGRAM_ID")
    if not admin_telegram_id_str or not admin_telegram_id_str.isdigit():
        raise ValueError("ADMIN_TELEGRAM_ID must be set in .env")
    admin_telegram_id = int(admin_telegram_id_str)

    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        groq_vision_model=os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        portal_username=os.getenv("PORTAL_USERNAME", ""),
        portal_password=os.getenv("PORTAL_PASSWORD", ""),
        admin_telegram_id=admin_telegram_id,
    )
