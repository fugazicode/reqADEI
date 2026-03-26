# Automated Tenant Verification Telegram Bot

## Overview
A Telegram bot that automates the Delhi Police CCTNS tenant verification process. It collects Aadhaar card data from landlords and tenants via OCR and AI, verifies the data interactively, then uses a headless browser to fill and submit the official form on the Delhi Police portal.

## Architecture
- **Language**: Python 3.12
- **Telegram Framework**: aiogram 3.x (async)
- **Web Automation**: Playwright (Chromium headless)
- **OCR**: OCR.space API
- **AI Parsing**: Groq (Llama 3.3)
- **Data Validation**: Pydantic v2
- **PDF Handling**: pypdf, fpdf2

## Project Layout
- `main.py` — Entry point; sets up bot, dispatcher, routers, background workers
- `core/` — Pipeline engine and processing stages
- `features/` — Bot workflow modules (identity_collection, data_verification, extras_collection, submission)
- `infrastructure/` — External service clients (OCR, Groq, session store, refund ledger)
- `shared/` — Config, logger, Pydantic models
- `utils/` — Helpers (Aadhaar validation, address parsing, station lookup)
- `prompts/` — LLM system prompts
- `data/` — Static data (police_stations.json)
- `tests/` — Test suite with mock portal server

## Workflow
- **Name**: `Start application`
- **Command**: `python main.py`
- **Type**: Console (no frontend/web UI)

## Required Secrets
| Secret | Description |
|--------|-------------|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `OCR_SPACE_API_KEY` | API key from ocr.space |
| `GROQ_API_KEY` | API key from groq.com |
| `PORTAL_USERNAME` | Delhi Police CCTNS portal username |
| `PORTAL_PASSWORD` | Delhi Police CCTNS portal password |
| `ADMIN_TELEGRAM_ID` | Numeric Telegram user ID for admin notifications |

## Optional Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model to use |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `STARS_PRICE` | `35` | Telegram Stars price for document delivery |
| `PAYMENT_TEST_MODE` | `false` | Enable test payment mode |
