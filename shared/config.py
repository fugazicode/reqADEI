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
    worker_url: str = ""
    worker_secret: str = ""
    telegram_webhook_secret: str = ""
    tunnel_url: str = ""
    local_webhook_port: int = 8080
    local_webhook_path: str = "/webhook"


def load_settings() -> Settings:
    load_dotenv()
    admin_telegram_id_str = os.getenv("ADMIN_TELEGRAM_ID")
    if not admin_telegram_id_str or not admin_telegram_id_str.isdigit():
        raise ValueError("ADMIN_TELEGRAM_ID must be set in .env")
    admin_telegram_id = int(admin_telegram_id_str)

    raw_snapshot_dir = os.getenv("SUBMISSION_SNAPSHOT_DIR", "").strip()
    snapshot_dir = Path(raw_snapshot_dir) if raw_snapshot_dir else None

    local_webhook_port_str = os.getenv("LOCAL_WEBHOOK_PORT", "8080")
    local_webhook_port = int(local_webhook_port_str) if local_webhook_port_str.isdigit() else 8080

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
        worker_url=os.getenv("WORKER_URL", "").rstrip("/"),
        worker_secret=os.getenv("WORKER_SECRET", ""),
        telegram_webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET", ""),
        tunnel_url=os.getenv("TUNNEL_URL", "").rstrip("/"),
        local_webhook_port=local_webhook_port,
        local_webhook_path=os.getenv("LOCAL_WEBHOOK_PATH", "/webhook"),
    )
