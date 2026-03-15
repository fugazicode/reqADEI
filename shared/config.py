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



def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        ocr_space_api_key=os.getenv("OCR_SPACE_API_KEY", ""),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
