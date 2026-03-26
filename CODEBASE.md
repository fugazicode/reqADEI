# Codebase Documentation
## Delhi Police CCTNS Tenant Verification Bot

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [Project Structure](#3-project-structure)
4. [End-to-End User Flow](#4-end-to-end-user-flow)
5. [Module Reference](#5-module-reference)
   - [Entry Point — `main.py`](#51-entry-point--mainpy)
   - [Core Pipeline — `core/`](#52-core-pipeline--core)
   - [Features — `features/`](#53-features--features)
   - [Infrastructure — `infrastructure/`](#54-infrastructure--infrastructure)
   - [Shared — `shared/`](#55-shared--shared)
   - [Utilities — `utils/`](#56-utilities--utils)
   - [Tests — `tests/`](#57-tests--tests)
6. [Data Models](#6-data-models)
7. [State Machine (FSM)](#7-state-machine-fsm)
8. [Key Design Decisions](#8-key-design-decisions)
9. [Configuration & Secrets](#9-configuration--secrets)
10. [Logging & Audit Trail](#10-logging--audit-trail)

---

## 1. Project Overview

This is an **asynchronous Telegram bot** that automates the **Delhi Police CCTNS (Crime and Criminal Tracking Network & Systems) tenant verification process**. The bot:

- Collects Aadhaar card images from landlords (owners) and tenants via Telegram
- Runs them through an OCR → AI parsing pipeline to extract personal and address data
- Presents each extracted field to the user for interactive confirmation or correction
- Collects supplemental information (occupation, tenancy purpose, rental address)
- Submits the completed form to the **Delhi Police CCTNS portal** using a headless browser
- Retrieves the official PDF, applies a watermark, sends a preview, and delivers the clean copy after payment via **Telegram Stars**

The bot is designed with a strong human-in-the-loop philosophy: no data is submitted to the government portal until the user has explicitly confirmed every required field.

---

## 2. Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Telegram Framework | `aiogram` 3.x (async, FSM-based) |
| Web Automation | `playwright` (Chromium headless) |
| OCR | OCR.space REST API |
| LLM / AI Parsing | Groq API (`llama-3.3-70b-versatile`) |
| Data Validation | `pydantic` v2 |
| PDF Watermarking | `fpdf2` + `pypdf` |
| HTTP Client | `httpx` (async) |
| Configuration | `python-dotenv` |

---

## 3. Project Structure

```
.
├── main.py                          # Bot entry point
├── requirements.txt                 # Python dependencies
│
├── core/                            # Generic pipeline engine
│   ├── engine.py                    # PipelineEngine orchestrator
│   ├── pipeline_stages.py           # ImageExtractionStage, IdParsingStage
│   └── stage_interface.py           # Abstract PipelineStage base class
│
├── features/                        # User-facing workflow modules
│   ├── identity_collection/         # Consent + image upload handlers
│   │   ├── handlers.py
│   │   ├── keyboards.py
│   │   └── states.py
│   ├── data_verification/           # Field-by-field confirmation loop
│   │   ├── handlers.py
│   │   ├── confirmation_flow.py     # ConfirmationFlow queue manager
│   │   ├── friction.py              # HIGH_FRICTION_FIELDS (double-confirm)
│   │   ├── keyboards.py
│   │   └── states.py
│   ├── extras_collection/           # Occupation, tenancy purpose, address
│   │   ├── handlers.py
│   │   ├── keyboards.py
│   │   └── states.py
│   └── submission/                  # Portal automation & payment
│       ├── handlers.py              # Payment & refund command handlers
│       ├── submission_worker.py     # Background queue + Playwright orchestration
│       ├── form_filler.py           # CCTNS form filling logic
│       ├── portal_session.py        # Login + navigation to form
│       └── states.py
│
├── infrastructure/                  # External service clients
│   ├── vision_client.py             # OCR.space API wrapper
│   ├── groq_parser.py               # Groq LLM wrapper
│   ├── session_store.py             # In-memory session storage
│   └── refund_ledger.py             # Persistent JSON refund log
│
├── shared/                          # Common models and utilities
│   ├── config.py                    # Settings loader (env vars)
│   ├── logger.py                    # Logging configuration
│   ├── audit_log.py                 # Aadhaar processing audit trail
│   └── models/
│       ├── form_payload.py          # Pydantic models: FormPayload, OwnerData, TenantData, AddressData
│       └── session.py               # FormSession + ImageRecord dataclasses
│
├── utils/                           # Domain-specific helpers
│   ├── aadhaar.py                   # Verhoeff validation, OCR extraction, masking, side detection
│   ├── address_parser.py            # Address text utilities
│   ├── name_splitter.py             # Name parsing helpers
│   ├── payload_accessor.py          # Dot-path getter/setter for FormPayload
│   ├── station_lookup.py            # Colony → district/station lookup from JSON
│   └── watermark.py                 # PDF watermark application
│
├── prompts/                         # LLM prompt templates
│   ├── id_extraction.txt            # Prompt to parse Aadhaar OCR text → JSON
│   └── address_parsing.txt          # Prompt to parse free-text address → JSON
│
├── data/
│   └── police_stations.json         # Static locality → district → station mapping
│
└── tests/                           # Test suite
    ├── mock_portal_server.py        # Local HTTP server simulating CCTNS portal
    ├── sample_payload.py            # Reusable test FormPayload fixture
    ├── test_full_fill.py
    ├── test_mock_submission.py
    ├── test_phase1.py  …  test_phase4_addresses.py
    └── test_retrieve_pdf.py
```

---

## 4. End-to-End User Flow

```
User sends /start
    │
    ▼
Consent prompt (inline keyboard: Agree / Disagree)
    │ Agree
    ▼
[IDENTITY COLLECTION — OWNER]
  Upload owner Aadhaar images (photo or document)
    │ Tap "Done"
    ▼
PipelineEngine.run(session)
  ├── ImageExtractionStage  → OCR.space API → raw text
  └── IdParsingStage        → Groq LLM → structured JSON → session.payload.owner
    │
    ▼
[DATA VERIFICATION — OWNER]
  ConfirmationFlow presents each field one at a time:
    owner.first_name, last_name, relative_name, relation_type,
    address.house_no, colony, village, district, police_station, pincode
  User clicks Confirm or Edit for each field.
  High-friction fields (names, district, police_station) require double confirmation.
    │ Queue empty
    ▼
[EXTRAS COLLECTION — OWNER]
  Inline keyboard: Select owner occupation
    │
    ▼
[IDENTITY COLLECTION — TENANT]
  Upload tenant Aadhaar images
    │ Tap "Done"
    ▼
PipelineEngine.run(session)
  (same pipeline, session.current_confirming_person = "tenant")
    │
    ▼
[DATA VERIFICATION — TENANT]
  ConfirmationFlow: first_name, last_name, Aadhaar no (masked), relative_name, relation_type, dob
    │
    ▼
[EXTRAS COLLECTION — TENANT]
  Inline keyboard: Select tenancy purpose
  Free-text: Type the full tenanted address
    │
    ▼
Groq parses address → structured fields
StationLookup suggests district + police station
ConfirmationFlow: confirm/edit tenanted address fields
    │ All confirmed
    ▼
[SUBMISSION]
FormPayload.is_submittable() == True
SubmissionWorker.enqueue(job)  →  User sees queue position
    │
    ▼  (background worker)
PortalSession.open()
  → Launch Chromium headless
  → Navigate to delhipolice.gov.in
  → Click "Domestic Help/Tenant Registration" (opens new tab)
  → Fill login form (j_username, j_password)
  → Navigate to addtenantpgverification.htm
    │
    ▼
FormFiller.fill(image_bytes)
  ├── _fill_owner_tab()                 Owner personal details
  ├── _fill_tenant_personal_tab()       Tenant personal details
  ├── _navigate_to_address_subtab()     Switch to Address sub-tab
  ├── _fill_tenant_address_tenanted()   Tenanted premises address
  ├── _fill_tenant_address_permanent()  Tenant's permanent address
  ├── _fill_family_member_tab()         Family members
  ├── _fill_document_upload(image_bytes) Upload tenant ID photo
  ├── _fill_affidavit_tab()             Affidavit/declaration
  └── _submit_and_get_result()          Submit → capture request number
    │
    ▼
_retrieve_pdf(request_number)  →  Download generated PDF
apply_watermark(pdf_bytes)     →  Overlay tiled "PREVIEW" text
Send watermarked PDF to user
    │
    ▼
[PAYMENT]
Send Telegram Stars invoice (currency: XTR, default price: 35 Stars)
    │ User pays
    ▼
handle_successful_payment()
  → Pop clean PDF from _pending_deliveries
  → Send clean PDF to user
  → Log RefundEntry to refund_ledger.json (status: "eligible")
  → Clear payment timeout task
```

---

## 5. Module Reference

### 5.1 Entry Point — `main.py`

**Purpose:** Bootstraps and runs the entire bot.

**Key responsibilities:**
- Loads settings via `load_settings()` and configures logging
- Instantiates all shared services: `Bot`, `SessionStore`, `VisionClient`, `GroqParser`, `StationLookup`, `RefundLedger`, `SubmissionWorker`
- Creates two independent `PipelineEngine` instances (`owner_engine`, `tenant_engine`) so owner and tenant processing are isolated
- Injects all services into the `Dispatcher` as middleware dependencies (aiogram's dependency injection)
- Registers all routers in priority order: `root_router`, `submission_handlers`, `identity_collection_router`, `data_verification_router`, `extras_collection_router`
- On startup, launches two asyncio background tasks:
  - `_session_cleanup_loop` — purges sessions older than 24 hours every hour
  - `submission_worker.start()` — runs the Playwright queue processor

**Global commands (root_router):**
- `/start` — clears any existing state/session, creates a fresh `FormSession`, sends consent prompt
- `/cancel` — clears state and session at any point in the flow

**OCR preflight:** On startup, calls `vision_client.validate_api_key()` using a 1×1 transparent PNG probe image to detect invalid API keys before the first real user interaction.

---

### 5.2 Core Pipeline — `core/`

#### `core/stage_interface.py`
Defines the abstract base class `PipelineStage` with:
- `name: str` — unique identifier used for ordering
- `async execute(session: FormSession) -> FormSession` — transform and return the session

#### `core/engine.py` — `PipelineEngine`

Runs a fixed sequence of stages against a `FormSession`. Stages always execute in the order `["extract_images", "parse_id"]` regardless of registration order. Any remaining stages follow after.

If any stage raises an exception, the error is caught, stored in `session.last_error`, and processing stops. The calling handler then checks `session.last_error` to report the failure.

```python
engine = PipelineEngine([ImageExtractionStage(...), IdParsingStage(...)])
session = await engine.run(session)
if session.last_error:
    # handle failure
```

#### `core/pipeline_stages.py`

**`ImageExtractionStage`** (`name = "extract_images"`)

Processes all images uploaded for `session.current_confirming_person`:
1. Downloads each image file from Telegram via `bot.download(file_id)`
2. Calls `VisionClient.extract_text(image_bytes)` → raw OCR text
3. Runs `extract_aadhaar_from_text()` to find candidate Aadhaar numbers
4. Calls `classify_side()` to label images as `"front"` / `"back"` / `"unknown"`
5. Sets `ocr_confidence` (0.85 = one clean hit, 0.5 = ambiguous, 0.2 = none found)
6. Appends warnings like `"no_aadhaar_found"` or `"multiple_candidates"` to `record.extraction_warnings`
7. Detects if two different Aadhaar numbers were uploaded for the same person (conflict error)
8. Links front/back image pairs by matching Aadhaar suffix or by media group ID
9. Writes an `"image_processed"` event to `audit.log`
10. After processing, redacts `image_id` fields in the session to `"redacted"` for privacy

**`IdParsingStage`** (`name = "parse_id"`)

1. Validates that `session.raw_ocr_text` is non-empty
2. Calls `GroqParser.parse(raw_text, "id_extraction")` using the LLM
3. Cross-checks the extracted Aadhaar suffix against the other person's records — if the same Aadhaar appears for both owner and tenant, the session is failed with a conflict error
4. Maps the parsed dict into `session.payload.owner.*` or `session.payload.tenant.*` using `PayloadAccessor.set()`
5. For tenants, auto-sets `address_verification_doc_type = "Aadhar Card"` if not present
6. Clears `raw_ocr_text` after parsing

---

### 5.3 Features — `features/`

#### `features/identity_collection/`

**States (`states.py`):**
- `AWAITING_CONSENT`
- `OWNER_UPLOAD`
- `TENANT_UPLOAD`

**Handlers (`handlers.py`):**

| Handler | Trigger | Action |
|---|---|---|
| `consent_agree` | Callback `consent:agree` in `AWAITING_CONSENT` | Records `consent_given_at`, transitions to `OWNER_UPLOAD` |
| `collect_owner_photo` | Photo/Document in `OWNER_UPLOAD` | Appends `ImageRecord` to session, debounced edit of upload-count message |
| `owner_upload_done` | Callback `upload_done` in `OWNER_UPLOAD` | Runs `owner_engine`, transitions to `DataVerificationStates.CONFIRMING_FIELD` |
| `collect_tenant_photo` | Photo/Document in `TENANT_UPLOAD` | Same pattern as owner |
| `tenant_upload_done` | Callback `upload_done` in `TENANT_UPLOAD` | Runs `tenant_engine`, saves tenant front-image bytes for portal upload |

**Debounce pattern:** When multiple images arrive in a Telegram media group, the handler creates a new asyncio task to update the status message after a 0.2-second delay, cancelling any previous pending task. This prevents rate-limit errors from rapid message edits.

---

#### `features/data_verification/`

**States (`states.py`):**
- `CONFIRMING_FIELD` — waiting for user to click Confirm or Edit
- `AWAITING_EDIT_INPUT` — waiting for user to type a corrected value

**`confirmation_flow.py` — `ConfirmationFlow`**

Manages an ordered `session.confirmation_queue` (a list of dot-notation field paths). At each step:
1. Peeks at the first field in the queue
2. Gets its current value via `PayloadAccessor.get()`
3. If the value is missing → sets the field as `current_editing_field`, prompts user to type it, returns `"missing"`
4. If value exists → sends a message with `confirm_edit_keyboard(field_path)` showing the value, returns `"confirm"`

Aadhaar numbers are always displayed masked (`XXXX-XXXX-XXXX`) using `mask_aadhaar()`.

**Queue contents:**

*Owner queue:*
`owner.first_name`, `owner.last_name`, `owner.relative_name`, `owner.relation_type`, `owner.address.house_no`, `owner.address.colony_locality_area`, `owner.address.village_town_city`, `owner.address.district`, `owner.address.police_station`, `owner.address.pincode`

*Tenant queue:*
`tenant.first_name`, `tenant.last_name`, `tenant.address_verification_doc_no`, `tenant.relative_name`, `tenant.relation_type`, `tenant.dob`

**`friction.py` — High-Friction Fields**

The following fields require the user to click **Confirm twice** (double confirmation) before they are accepted:

```
owner.first_name, owner.last_name, owner.address.district, owner.address.police_station,
tenant.first_name, tenant.last_name, tenant.tenanted_address.district, tenant.tenanted_address.police_station
```

This protects against accidentally confirming a misread name or wrong police station. The FSM stores a `pending_double_confirm` key; the `confirm2:` callback handler checks this before popping the queue.

**Handlers (`handlers.py`):**

| Handler | Trigger | Action |
|---|---|---|
| `confirm_field` | Callback `confirm:<field_path>` | Pops queue (or triggers double-confirm for high-friction fields), calls `_next_step` |
| `confirm_field_second` | Callback `confirm2:<field_path>` | Final confirmation pop for high-friction fields |
| `edit_field` | Callback `edit:<field_path>` | Sets `current_editing_field`, transitions to `AWAITING_EDIT_INPUT` |
| `receive_edit_input` | Text message in `AWAITING_EDIT_INPUT` | Validates (Aadhaar checksum if doc number field), writes to payload, returns to confirmation flow |

**`_next_step()` routing logic:**
After the queue is exhausted, routes to the next workflow stage based on `session.next_stage`:
- `"owner_extras"` → `ExtrasCollectionStates.OWNER_OCCUPATION`
- `"tenant_extras"` → `ExtrasCollectionStates.TENANT_EXTRAS`
- `"submission"` → validates `is_submittable()`, enqueues `SubmissionJob`

---

#### `features/extras_collection/`

**States (`states.py`):**
- `OWNER_OCCUPATION` — waiting for owner occupation selection
- `TENANT_EXTRAS` — waiting for tenancy purpose selection
- `TENANTED_ADDRESS_INPUT` — waiting for free-text address
- `TENANTED_ADDRESS_CONFIRM` — confirming parsed address fields

**Handlers (`handlers.py`):**

| Handler | Trigger | Action |
|---|---|---|
| `set_owner_occupation` | Callback `occupation:<value>` | Sets `owner.occupation`, transitions to `TENANT_UPLOAD` |
| `set_tenant_purpose` | Callback `purpose:<value>` | Sets `tenant.purpose_of_tenancy`, transitions to `TENANTED_ADDRESS_INPUT` |
| `receive_tenanted_address` | Text in `TENANTED_ADDRESS_INPUT` | Parses address with Groq, runs `StationLookup`, builds confirmation queue for address fields |
| `pick_station` | Callback `station:<name>` or `station:__skip__` | Sets police station from suggested list or skips to manual confirm |

**Address parsing flow:**
1. User types the full address as free text
2. `GroqParser.parse(text, "address_parsing")` → structured dict with keys matching `AddressData` fields
3. Defaults `country = "India"` and `state = "Delhi"` if not found
4. `StationLookup.suggest(colony, district)` → tries exact colony name match in `police_stations.json`
5. If multiple stations are possible for the inferred district → shows an inline keyboard with options
6. Builds a confirmation queue: `house_no`, `street_name`, `colony_locality_area`, `village_town_city`, `tehsil_block_mandal`, `district`, `police_station`, `pincode`
7. Sets `session.next_stage = "submission"`

---

#### `features/submission/`

**States (`states.py`):**
- `COMPLETE` — form submitted or queued
- `AWAITING_PAYMENT` — clean PDF is ready, waiting for Stars payment

**`portal_session.py` — `PortalSession`**

Manages the Chromium browser lifecycle for one form submission:
- `open()` — launches browser, calls `_login()` then `_navigate_to_form()`, returns the `Page` object
- `close()` — closes browser gracefully (silently ignores Playwright errors on already-closed browsers)
- `_login()` — navigates to `delhipolice.gov.in`, clicks "Domestic Help/Tenant Registration" (which opens a new tab), fills `j_username` / `j_password`, clicks submit
- `_navigate_to_form()` — hovers the "Tenant Registration" menu, clicks `addtenantpgverification.htm`, waits for `[name="ownerFirstName"]` to confirm the form loaded

**`form_filler.py` — `FormFiller`**

The most complex component. Fills a multi-tab government form with AJAX-driven dropdowns.

**Static lookup tables (module-level):**
- `DISTRICT_VALUES` — maps district name string → portal numeric ID (e.g., `"SOUTH": "8167"`)
- `POLICE_STATION_VALUES` — maps station name → portal numeric ID (e.g., `"HAUZ KHAS": "8167017"`)
- `STATE_VALUES` — maps state name → portal numeric ID (e.g., `"DELHI": "8"`)

These IDs are specific to the CCTNS portal's form option values and must be kept in sync if the portal is ever updated.

**`fill(image_bytes)` — main entry point:**
Calls each section in order:
1. `_fill_owner_tab()` — owner personal fields
2. `_fill_tenant_personal_tab()` — tenant name, DOB, gender, Aadhaar, occupation, purpose
3. `_navigate_to_address_subtab()` — clicks Address sub-tab within Tenant section
4. `_fill_tenant_address_tenanted()` — rental property address fields + AJAX district/station
5. `_fill_tenant_address_permanent()` — tenant's home address + state → district AJAX chain
6. `_fill_family_member_tab()` — family member section
7. `_fill_document_upload(image_bytes)` — uploads tenant ID photo as a file
8. `_fill_affidavit_tab()` — ticks affidavit declaration
9. `_submit_and_get_result()` — clicks Submit, captures the request number from the confirmation page

**CSRF injection — `_setup_ajax_csrf()`:**

The portal uses AJAX for cascading dropdowns (state → district → police station). Each AJAX request requires an `X-XSRF-TOKEN` header matching the current session cookie. In a headless browser this header is normally absent, causing the AJAX calls to fail silently.

The solution:
1. Reads the `XSRF-TOKEN` cookie value via `page.evaluate()`
2. Registers a Playwright **route interceptor** on `**/getstates.htm`, `**/getdistricts.htm`, and `**/getpolicestations.htm`
3. For every matching request, the interceptor re-reads the live cookie value and injects it as `X-XSRF-TOKEN` before forwarding the request

**`_select_district_and_station()`:**

The dropdown chain for district/police station involves:
1. Triggering the district `<select>` change via `_js_select()` (sets value and dispatches a `change` event)
2. Waiting for the `getpolicestations.htm` AJAX response using `page.expect_response()`
3. Waiting for the station dropdown options to populate
4. Selecting the station by value; falling back to label if the numeric ID isn't found
5. Checking hidden input fields (`hidtenantPrestDistrict`, `hidtenantPresPStation`) that the portal uses for actual submission — force-setting them if they're empty after the AJAX flow

**`submission_worker.py` — `SubmissionWorker`**

An always-running background service that processes one form at a time:

- **Queue:** `asyncio.Queue[SubmissionJob]` — FIFO, returns queue size to caller as position number
- **Playwright lifetime:** A single `async with async_playwright() as pw` context wraps the entire worker lifetime, keeping Playwright initialized while jobs are processed sequentially
- **`_process_job(job, pw)`:**
  1. Creates a `PortalSession` and runs `FormFiller.fill()`
  2. Calls `_retrieve_pdf(request_number)` to download the generated document
  3. Applies watermark and sends preview to user via `bot.send_document()`
  4. In **test mode** (`PAYMENT_TEST_MODE=true`): sends clean PDF immediately, records a test `RefundEntry`
  5. In **normal mode**: sends a Telegram Stars invoice, stores clean PDF bytes in `_pending_deliveries[user_id]`, sets FSM state to `AWAITING_PAYMENT`, starts a 30-minute timeout task
  6. On any exception: sends an error message to the user

- **Payment timeout:** `_payment_timeout()` — after 30 minutes without payment, purges the pending delivery, notifies the user, and clears FSM state

**`handlers.py` — Payment & Refund Commands:**

| Handler | Trigger | Access |
|---|---|---|
| `handle_pre_checkout` | `PreCheckoutQuery` | All users |
| `handle_successful_payment` | `SuccessfulPayment` in `AWAITING_PAYMENT` | All users |
| `/test_invoice` | Text command | Admin only (`admin_telegram_id`) |
| `/refund` | Text command | All users (within 7-day window) |
| `/approve_refund <charge_id>` | Text command | Admin only |
| `/reject_refund <charge_id> <reason>` | Text command | Admin only |

**Refund flow:**
1. User sends `/refund` → bot checks `RefundLedger` for an `"eligible"` or `"requested"` entry within 7 days
2. Status updated to `"requested"`, admin notified with charge ID and suggested approval/rejection commands
3. Admin sends `/approve_refund <charge_id>` → `bot.refund_star_payment()` called, status updated to `"approved"`, user notified
4. Admin sends `/reject_refund <charge_id> <reason>` → status updated to `"rejected"`, user notified with reason

---

### 5.4 Infrastructure — `infrastructure/`

#### `vision_client.py` — `VisionClient`

Wraps the OCR.space REST API (`https://api.ocr.space/parse/image`).

- **`_normalize_api_key()`** — strips quotes, handles keys pasted as full URLs or `apikey=...` config strings
- **`extract_text(image_bytes)`** — encodes image as base64, posts with `OCREngine=2` (more accurate), returns concatenated `ParsedText` from all `ParsedResults`
- **`validate_api_key()`** — sends a 1×1 transparent PNG probe; raises `VisionConfigurationError` on invalid key, `VisionServiceUnavailable` on network/timeout issues

**Custom exceptions:**
- `VisionConfigurationError` — invalid or missing API key (fatal, re-raised from `main.py`)
- `VisionServiceUnavailable` — temporary network issue (logged as warning, non-fatal at startup)
- `VisionExtractionError` — API-level error during extraction

---

#### `groq_parser.py` — `GroqParser`

Wraps the Groq async API for structured data extraction.

- **`parse(raw_text, prompt_template_name)`:**
  1. Reads `prompts/<prompt_template_name>.txt`
  2. Substitutes `{raw_text}` with actual OCR output
  3. Calls `groq.chat.completions.create()` with `temperature=0` and system prompt `"Return only valid JSON."`
  4. Passes response through `_parse_json()` for robust extraction

- **`_parse_json(content)`** — handles LLM responses that wrap JSON in markdown code fences (\`\`\`json ... \`\`\`), finds the first `{` or `[` and last `}` or `]`, and parses the extracted substring

---

#### `session_store.py` — `SessionStore`

In-memory dictionary (`dict[int, FormSession]`) keyed by Telegram user ID.

- **`get(user_id)`** — returns `FormSession | None`
- **`save(session)`** — stores session, updates `_last_activity` timestamp
- **`delete(user_id)`** — removes session and timestamp
- **`cleanup_expired(ttl_seconds=86400)`** — called every hour; removes sessions with no activity in 24 hours

> **Note:** Sessions are not persisted to disk. A bot restart clears all in-progress sessions.

---

#### `refund_ledger.py` — `RefundLedger`

Persistent JSON file (`refund_ledger.json`) tracking payment and refund status.

**`RefundEntry` fields:** `charge_id`, `user_id`, `request_number`, `paid_at`, `status`, `reason`, `test_mode`

**Status lifecycle:** `"eligible"` → `"requested"` → `"approved"` or `"rejected"`

Writes are atomic: the ledger is written to a `.tmp` file and then renamed to replace the original, preventing corruption if the process is interrupted mid-write.

---

### 5.5 Shared — `shared/`

#### `config.py` — `Settings`

Frozen dataclass loaded from environment variables (`.env` file or Replit Secrets):

| Field | Env Var | Default |
|---|---|---|
| `bot_token` | `BOT_TOKEN` | — |
| `ocr_space_api_key` | `OCR_SPACE_API_KEY` | — |
| `groq_api_key` | `GROQ_API_KEY` | — |
| `groq_model` | `GROQ_MODEL` | `llama-3.3-70b-versatile` |
| `log_level` | `LOG_LEVEL` | `INFO` |
| `portal_username` | `PORTAL_USERNAME` | — |
| `portal_password` | `PORTAL_PASSWORD` | — |
| `stars_price` | `STARS_PRICE` | `35` |
| `payment_test_mode` | `PAYMENT_TEST_MODE` | `false` |
| `admin_telegram_id` | `ADMIN_TELEGRAM_ID` | — (required, must be numeric) |

`ADMIN_TELEGRAM_ID` is required at startup; the bot will refuse to start if it is missing or non-numeric.

---

#### `shared/models/form_payload.py`

Pydantic v2 models representing the form data being collected.

```
FormPayload
├── owner: OwnerData
│   ├── first_name, middle_name, last_name
│   ├── relative_name, relation_type
│   ├── dob, mobile_no
│   ├── address_verification_doc_no   (Aadhaar number)
│   ├── occupation
│   └── address: AddressData
└── tenant: TenantData
    ├── first_name, middle_name, last_name
    ├── gender, occupation
    ├── relative_name, relation_type
    ├── dob
    ├── address_verification_doc_type  (default: "Aadhar Card")
    ├── address_verification_doc_no    (Aadhaar number)
    ├── purpose_of_tenancy
    ├── address: AddressData           (permanent home address)
    ├── previous_address: AddressData
    └── tenanted_address: AddressData  (rental property address)

AddressData
    house_no, street_name, colony_locality_area
    village_town_city, tehsil_block_mandal
    district, police_station, pincode, state, country
```

`FormPayload.is_submittable()` enforces the minimum required fields before a job is enqueued:
- Owner: `first_name`, `last_name`, `occupation`
- Tenant: `first_name`, `last_name`, `purpose_of_tenancy`, `address_verification_doc_type`
- Tenanted address: `village_town_city`, `country`, `state`, `district`, `police_station`

All fields use `validate_assignment=True` so Pydantic validates data on every set operation.

---

#### `shared/models/session.py`

**`ImageRecord`** — tracks metadata for one uploaded image:
- `image_id` — Telegram file ID (redacted to `"redacted"` after processing)
- `person` — `"owner"` or `"tenant"`
- `side` — `"front"`, `"back"`, or `"unknown"`
- `extracted_aadhaar_suffix` — last 4 digits if extracted
- `ocr_confidence` — float (0.2 / 0.5 / 0.85)
- `media_group_id` — links images sent in the same Telegram album
- `linked_to_image_id` — matched front↔back pair
- `extraction_warnings` — list of warning strings

**`FormSession`** — the central state object for one user's session:
- `telegram_user_id` — primary key
- `payload: FormPayload` — the structured data being built
- `image_records: list[ImageRecord]` — all uploaded images
- `consent_given_at` — timestamp of user's consent
- `raw_ocr_text` — temporary buffer between pipeline stages (cleared after parsing)
- `tenant_image_bytes` — front-image bytes saved for portal upload
- `confirmation_queue: list[str]` — ordered dot-path fields awaiting confirmation
- `current_editing_field` — dot-path of field being edited
- `current_confirming_person` — `"owner"` or `"tenant"`
- `next_stage` — routing signal for `_next_step()` (`"owner_extras"`, `"tenant_extras"`, `"submission"`)
- `edit_return_state` / `edit_return_person` — one-level navigation stack for returning after edit
- `last_error` — set by pipeline engine when a stage fails

`owner_image_file_ids` and `tenant_image_file_ids` are properties that read/write `image_records` by person filter. They are excluded from dataclass serialization.

---

#### `shared/audit_log.py`

Writes a JSON-formatted audit trail to `audit.log` for every Aadhaar image processed. Each event includes: event type, person, image ID, timestamp, side, Aadhaar suffix (if found), OCR confidence, warnings, and linked image pairing.

Event types: `"image_processed"`, `"conflict_detected"`

---

### 5.6 Utilities — `utils/`

#### `aadhaar.py`

Complete Aadhaar number processing with no external dependencies.

**`validate_aadhaar(number)`:**
1. Strips spaces and dashes
2. Applies OCR substitutions: `O→0`, `I→1`, `l→1`, `S→5`, `B→8`
3. Checks: exactly 12 digits, first digit is 2–9, not all same digit, not `123456789012`
4. Runs the **Verhoeff checksum algorithm** (dihedral group D5) using the multiplication table `d`, permutation table `p`, and inverse table `inv`
5. Returns `(True, cleaned)` or `(False, "")`

**`extract_aadhaar_from_text(ocr_text)`:**
Applies OCR substitutions, strips whitespace/dashes, finds all 12+ digit runs, validates each as a potential Aadhaar number, returns deduplicated valid numbers.

**`classify_side(ocr_text, qr_decoded)`:**
Uses keyword heuristics (address indicators: `"s/o"`, `"d/o"`, `"village"`, `"district"`, `"pin"`, etc.) and regex patterns (DOB format, proper names) to classify image as front or back. QR-decoded images are always classified as back.

**`mask_aadhaar(number)`:**
Accepts full 12-digit number or 4-digit suffix; returns `"XXXX-XXXX-XXXX"` format.

---

#### `payload_accessor.py` — `PayloadAccessor`

Provides dot-notation path access to the nested Pydantic model tree:

- **`get(payload, "tenant.address.district")`** — walks the model tree, returns `None` on any missing intermediate
- **`set(payload, "tenant.address.district", "SOUTH")`** — walks the tree, auto-creating intermediate Pydantic model instances (`AddressData()`, `OwnerData()`, etc.) as needed using model field type annotations

This is what allows pipeline stages and handlers to write `PayloadAccessor.set(session.payload, f"{prefix}.{key}", value)` without caring about the exact nesting structure.

---

#### `station_lookup.py` — `StationLookup`

Loads `data/police_stations.json` (a list of `{locality, district, police_station}` objects) and provides:

- **`suggest(colony_locality_area, district)`** — exact lowercase match of locality name → returns `(district, station)` tuple; falls back to returning the passed district with no station
- **`stations_for_district(district)`** — returns sorted list of all station names in a district (for the selection keyboard)

---

#### `watermark.py` — `apply_watermark(pdf_bytes, text="PREVIEW")`

Creates an A4-sized FPDF overlay with tiled, 45°-rotated grey "PREVIEW" text (every 160×120 pt grid), then merges it onto every page of the input PDF using `pypdf`. Returns original bytes unchanged if the input is not a valid PDF.

---

### 5.7 Tests — `tests/`

#### `mock_portal_server.py`

A local Python HTTP server that mimics the CCTNS portal's HTTP interface. Serves fake login pages, form pages, AJAX endpoints (`getstates.htm`, `getdistricts.htm`, `getpolicestations.htm`), and a dummy PDF download. Used by tests to validate `FormFiller` and `PortalSession` without hitting the live government website.

#### Test files

| File | What it tests |
|---|---|
| `test_phase1.py` | Owner image upload and OCR extraction |
| `test_phase2.py` | Owner data verification/confirmation flow |
| `test_phase3_tenant.py` | Tenant image upload and extraction |
| `test_phase4_addresses.py` | Tenanted address parsing and station lookup |
| `test_full_fill.py` | Complete `FormFiller.fill()` against mock portal |
| `test_mock_submission.py` | `SubmissionWorker` end-to-end with mock portal |
| `test_retrieve_pdf.py` | PDF download and retrieval after form submission |
| `sample_payload.py` | Reusable test `FormPayload` with realistic Delhi data |

---

## 6. Data Models

### Relationship diagram

```
FormSession ─────────── has one ─────────── FormPayload
    │                                            │
    ├── list[ImageRecord]           ┌────────────┼────────────┐
    │   (one per uploaded image)    │            │            │
    │                            OwnerData   TenantData   AddressData
    ├── confirmation_queue                         │         (×3: address,
    │   list[str] (dot paths)            tenanted_address,    previous_address,
    │                                    previous_address)    tenanted_address)
    └── payload ─ (root of dot-path tree)
```

---

## 7. State Machine (FSM)

The bot uses aiogram's built-in FSM. States are grouped by feature:

```
IdentityCollectionStates
    AWAITING_CONSENT
    OWNER_UPLOAD
    TENANT_UPLOAD

DataVerificationStates
    CONFIRMING_FIELD
    AWAITING_EDIT_INPUT

ExtrasCollectionStates
    OWNER_OCCUPATION
    TENANT_EXTRAS
    TENANTED_ADDRESS_INPUT
    TENANTED_ADDRESS_CONFIRM

SubmissionStates
    COMPLETE
    AWAITING_PAYMENT
```

**Transitions:**

```
AWAITING_CONSENT ──[consent:agree]──► OWNER_UPLOAD
OWNER_UPLOAD ──[upload_done]──► CONFIRMING_FIELD (owner queue)
CONFIRMING_FIELD ──[queue empty, next=owner_extras]──► OWNER_OCCUPATION
OWNER_OCCUPATION ──[occupation selected]──► TENANT_UPLOAD
TENANT_UPLOAD ──[upload_done]──► CONFIRMING_FIELD (tenant queue)
CONFIRMING_FIELD ──[queue empty, next=tenant_extras]──► TENANT_EXTRAS
TENANT_EXTRAS ──[purpose selected]──► TENANTED_ADDRESS_INPUT
TENANTED_ADDRESS_INPUT ──[address parsed]──► TENANTED_ADDRESS_CONFIRM
TENANTED_ADDRESS_CONFIRM ──[queue empty, next=submission]──► COMPLETE
COMPLETE ──[worker sends invoice]──► AWAITING_PAYMENT
AWAITING_PAYMENT ──[payment received]──► COMPLETE

[any state] + CONFIRMING_FIELD ──[field missing or edit clicked]──► AWAITING_EDIT_INPUT
AWAITING_EDIT_INPUT ──[text received]──► (return_state, continue queue)

[any state] + /cancel ──► (state cleared)
[any state] + /start ──► AWAITING_CONSENT
```

---

## 8. Key Design Decisions

### Human-in-the-loop confirmation
Every field extracted by OCR/LLM is shown to the user before submission. The bot never submits data silently. This compensates for OCR inaccuracies and LLM hallucinations.

### Double confirmation for critical fields
Names and police station fields use `HIGH_FRICTION_FIELDS` requiring two separate button clicks. A single misread name or wrong station would make the government document invalid.

### CSRF token injection for AJAX dropdowns
The CCTNS portal loads district and station dropdowns via AJAX with CSRF protection. The headless browser cannot automatically replay this token. The Playwright route interceptor reads the live cookie on every matching request and injects it, making the AJAX chain work identically to a real browser session.

### Pipeline engine error isolation
By catching all exceptions in `PipelineEngine.run()` and storing them in `session.last_error`, the handler code only needs to check one field to determine success/failure. This prevents unhandled exceptions from crashing the bot and allows graceful user-facing error messages.

### Aadhaar number cross-validation
Before committing parsed data, `IdParsingStage` checks whether the tenant's Aadhaar suffix overlaps with the owner's. If the same card is uploaded for both roles (a common user mistake), the session is failed with a clear explanation.

### Image ID redaction
After the pipeline processes an image, its Telegram `file_id` is overwritten with `"redacted"` in the session. This prevents the session store from holding unnecessary references to potentially sensitive file references.

### Atomic ledger writes
`RefundLedger` writes to a `.tmp` file and renames it to replace the real file. This is a standard pattern that prevents ledger corruption if the process terminates mid-write.

### Single Playwright instance
`SubmissionWorker` wraps the entire worker loop in a single `async with async_playwright()` context. Launching Playwright once and reusing it for all jobs is significantly cheaper than launching a new browser instance per job.

---

## 9. Configuration & Secrets

All secrets are managed via environment variables (Replit Secrets or a `.env` file in development).

| Secret | Required | Purpose |
|---|---|---|
| `BOT_TOKEN` | Yes | Telegram bot token from @BotFather |
| `OCR_SPACE_API_KEY` | Yes | API key from ocr.space |
| `GROQ_API_KEY` | Yes | API key from console.groq.com |
| `PORTAL_USERNAME` | Yes | Delhi Police CCTNS portal login |
| `PORTAL_PASSWORD` | Yes | Delhi Police CCTNS portal password |
| `ADMIN_TELEGRAM_ID` | Yes | Your numeric Telegram user ID |
| `GROQ_MODEL` | No | Default: `llama-3.3-70b-versatile` |
| `LOG_LEVEL` | No | Default: `INFO` |
| `STARS_PRICE` | No | Default: `35` (Telegram Stars) |
| `PAYMENT_TEST_MODE` | No | Default: `false`; if `true`, skips payment and delivers clean PDF immediately |

---

## 10. Logging & Audit Trail

**Application log** — written to stdout in the format:
```
2026-03-26 16:18:01,804 | INFO | aiogram.dispatcher | Start polling
```
Level is controlled by `LOG_LEVEL`. All aiogram, pipeline, and worker events are logged here.

**Audit log** — written to `audit.log` (JSON Lines format, one event per line):
```json
{
  "event_type": "image_processed",
  "person": "owner",
  "image_id": "AgAC...",
  "timestamp": 1743004081.5,
  "side": "front",
  "aadhaar_suffix": "3421",
  "ocr_confidence": 0.85,
  "qr_decoded": false,
  "extraction_warnings": [],
  "upload_timestamp": 1743004075.1,
  "linked_to_image_id": "AgAD..."
}
```
The audit log records every image processing event and any Aadhaar conflict detection, providing a compliance trail for Aadhaar data handling.

**Refund ledger** — `refund_ledger.json` (JSON array). Records every completed payment and its refund status lifecycle.
