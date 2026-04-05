# Codebase Context
_Auto-generated. Append-only — add entries at the bottom, never edit existing ones._

## main.py — aiogram app bootstrap and global wiring
_Explored: 2026-04-04_

- **Entry points**: `run()` (async entry from `if __name__ == "__main__"`); `cancel_root` handles `/cancel` in any FSM state.
- **Key abstractions**: `root_router` (only `/cancel`); `_build_pipeline` wraps a single `ImageParsingStage`; `_session_cleanup_loop` hourly `session_store.cleanup_expired()`.
- **Internal dependencies**: Registers four feature routers in order: `identity_collection`, `data_verification`, `address_collection` (submission is reached from data_verification, not a separate router here).
- **External dependencies**: `aiogram` (Bot, Dispatcher, Router, FSM), `asyncio`.
- **Gotchas**: All handler dependencies (`session_store`, `groq_parser`, `station_lookup`, `pipeline`, `analytics_store`, `bot`, `submission_worker`) are attached to `dp[...]` for middleware/DI-style injection; router order matters for handler resolution.

## scripts/ — CLI utilities for portal scrape and submission replay
_Explored: 2026-04-04_

- **Entry points**: `scrape_police_stations.py` `main()` (`--bootstrap` / `--scrape`); `run_submission_snapshot.py` `main()` (loads snapshot, runs `execute_playwright_submission`).
- **Key abstractions**: National JSON schema `by_state → { district: [stations] }`; scraper navigates tenant form → Permanent Address tab; snapshot runner reuses the same submission path as the bot worker.
- **Internal dependencies**: Scraper uses `PortalSession`, `shared.config.load_settings`, state list from `data/delhi_police_stations.json`; snapshot uses `infrastructure.submission_snapshot.load_snapshot` and `features.submission.submission_worker.execute_playwright_submission`.
- **External dependencies**: Playwright (`async_playwright`), `python-dotenv` in snapshot runner, `argparse`.
- **Gotchas**:
  - **Portal vs Playwright `select_option`**: The CCTNS tenant form loads district and police-station `<select>` options via AJAX after a state/district change. The page listens on **jQuery-style `change` handlers**. Playwright’s `page.select_option()` can change the selected value in the DOM **without** reliably firing those handlers on this legacy stack, so **`getdistricts` / `getpolicestations` never run**, dependent dropdowns stay empty, and a `wait_for_function` on `options.length > 1` appears “stuck” until it times out (often ~20s per state). **What matches the real portal**: set `select.value` in `page.evaluate` and `dispatchEvent(new Event('change', { bubbles: true }))`, same pattern as `FormFiller._js_select` in `features/submission/form_filler.py`.
  - **Waiting for data**: Production code wraps that JS select with `expect_response` (URLs containing `getdistricts` / `getpolicestations`) before assuming the next dropdown is populated; polling the DOM alone is insufficient if the AJAX never fired.
  - Scraper credentials: `PORTAL_USERNAME` / `PORTAL_PASSWORD` via `load_settings()` (`.env`).

## core/ — async pipeline for ID image OCR and payload merge
_Explored: 2026-04-04_

- **Entry points**: `PipelineEngine.run(session)` (invoked from identity handlers after upload confirm); `ImageParsingStage.execute(session)` is the only concrete stage today.
- **Key abstractions**: `PipelineStage` ABC (`name`, `execute`); `PipelineEngine` orders stages via `stage_order` (currently `["parse_image"]` only) then appends any remaining stages; on any exception sets `session.last_error` and stops. `ImageParsingStage` downloads Telegram images for `current_confirming_person`, calls Groq `id_extraction`, merges into `session.payload` via `PayloadAccessor`, validates Aadhaar and cross-person duplicate suffix, writes audit events.
- **Internal dependencies**: `GroqParser`, `FormSession` / `ImageRecord`, `PayloadAccessor`, `shared.portal_enums.STATES`, Delhi district normalisation aligned with `form_filler.DISTRICT_VALUES`, `shared.audit_log.write_audit_event`, `utils.aadhaar`.
- **External dependencies**: `aiogram.Bot` (file download).
- **Gotchas**: Skips writing `None` from parsed nested dicts so OCR does not wipe existing fields; tenant first image bytes cached on `session.tenant_image_bytes` for portal upload; default `tenant.address_verification_doc_type` to `"Aadhar Card"` if missing; auto-sets `address.country` to `INDIA` when absent; normalises state (abbrev → full name, uppercase) and Delhi-ish district strings via `_normalise_delhi_district`. Invalid Aadhaar or owner/tenant same-document conflict returns early with `last_error` and **does not** clear `image_records` (handlers own cleanup on error).

## infrastructure/ — in-memory sessions, analytics DB, Groq, snapshots
_Explored: 2026-04-04_

- **Entry points**: `SessionStore.get` / `set` / `delete` / `cleanup_expired` (sync-first API used by FSM handlers; async wrappers for worker); `SessionStore.user_lock` async context manager for per-telegram-user serialization; ID-upload debounce task registry (`cancel_upload_debounce`, `replace_upload_debounce_task`, `cancel_all_upload_debounces_for_user`). `GroqParser.parse` / `parse_image` load templates from `prompts_dir`, call Groq chat completions (text + vision with base64 JPEG data URLs). `AnalyticsStore.init` / `open_session` / field-edit and playwright run logging. `load_snapshot` / replay helpers in `submission_snapshot.py` for offline runs.
- **Key abstractions**: In-process `dict[int, FormSession]` with `_last_activity` TTL cleanup; per-user `asyncio.Lock` plus debounce `Task` map keyed by `(user_id, "owner"|"tenant")`; WAL-mode SQLite schema for sessions, field_edits, fsm_transitions, playwright_runs.
- **Internal dependencies**: `FormSession` from `shared.models.session`; snapshot types align with submission worker / `scripts/run_submission_snapshot.py`.
- **External dependencies**: `aiosqlite`, `groq.AsyncGroq`, `asyncio`.
- **Gotchas**: `delete` and `cleanup_expired` cancel upload debounce tasks and drop user locks to avoid leaks; debounce tasks must handle `CancelledError` in the coroutine body (callers in identity handlers). `GroqParser` assumes prompt files exist beside template name; vision path sends all images in one multimodal user message.
- **Not read in detail**: `vision_client.py`, full body of `submission_snapshot.py` beyond header/replay entry pattern.

### Update — infrastructure/
_Updated: 2026-04-04_

- **What changed**: Clarify `VisionClient` usage after grep.
- **Revised gotchas**: `vision_client.py` defines `VisionClient` but nothing in the repo imports it; live ID parsing uses `GroqParser.parse_image` via `ImageParsingStage`.

## features/submission/portal_session.py — Playwright login and form entry
_Explored: 2026-04-05_

- **Entry points**: `PortalSession.open()` → `_login` → `_navigate_to_form`; used by scraper and any code that needs an authenticated page on `cctns.delhipolice.gov.in`.
- **Gotchas**:
  - **`_login`**: After `#button`, `wait_for_load_state("domcontentloaded")` can resolve on an **early** redirect while the session cookie is still settling. Prefer **`wait_for_url`** (or equivalent) until the URL no longer indicates failure — portal maps failed auth to **`login.htm`** (see external `sessionhandler.js`: `continueSessionNoOption` → `location.href="login.htm"`).
  - **`_navigate_to_form`**: If the session is invalid, `goto` the tenant form can bounce to **`login.htm`** while the code still **`wait_for_selector`** on `ownerFirstName` for up to 5 minutes. Add a **post-`goto` URL guard** (e.g. `login.htm` or path not under expected `citizenservices`) before the long selector wait.
- **Note**: These issues are **not** the same as the **`select_option` vs `change`** AJAX problem on the tenant form (documented under **scripts/**); they are the **auth / navigation** layer only.

## Portal client JS (CCTNS citizen) — external behavior reference
_Explored: 2026-04-05 — sources: captured portal scripts (not vendored in this repo)._

Summarises JS that explains fancybox, tabs, country cascade, DOB, and validators — useful when debugging Playwright vs live portal.

- **`tab_control.js`**: `init()` registers **9** `TabView` instances (`TabView1`…`TabView9`). Links call `TabView.switchTab(TabViewIdx, TabIdx)`. Matches **`FormFiller`** using `TabView.switchTab(1, 1)` for Tenant → Address sub-tab.
- **`sessionhandler.js`**: Session expiry posts `sessionexpired.htm` then opens a **modal fancybox**; **`onStart`** disables most `:input` (except readonly / some exclusions). **`onCleanup`** re-enables. Long fills can hit expiry **before** submit — `form_filler._extract_fancybox_message` runs around **submit**, not between tabs (gap if mid-fill popups must be detected).
- **`countryselect.js`**: **`checkForOtherCountry`**: select value **`80`** = India. If **`value != 80`**, state / district / police `<select>`s are **emptied** and replaced with “not applicable” options; restoring India repopulates from saved snapshots. Aligns with **`form_filler`** comment: do not change owner country/state from defaults to avoid wiping cascaded selects. Multiple variants (`checkForOtherCountry1`/`2`/`signup`) target different hard-coded state IDs on other pages.
- **`commonagepanel.js`**: DOB is parsed as **DD/MM/YYYY** (`split('/')`, year = index 2). Valid entry sets age/YOB fields **`readOnly`** and age-range fields **`disabled`**. Out-of-range → **`fancyWarning`** + clear. Exception: **`tenantVerificationFamily`** skips minimum-age check.
- **`dateFormatValidation.js`**: **`validateDate`** enforces **dd/MM/yyyy**; invalid → **`fancyWarning`** and **clears** the field.
- **`commonAjaxValidator.js`**: Blur/post validators (`validatename.htm`, `validateAddressField.htm`, etc.) may **clear** fields or show **`fancyWarning`**. **`descriptionAjaxValidation`**: on “ok” path server can **overwrite** `input.value` with **`data.name`** (async; outer function **`return result`** is unreliable). **`nameNoHindiAjaxValidation` / `noHindiAjaxValidation`**: POST payload uses a likely typo **`"time=": timestamp`** instead of `time`.
- **`fancyalert.js`**: Modal fancybox **disables inputs** on open; **`fancyAlertwithSwitchTab` / `fancyWarningwithSwitchTab`** call **`TabView.switchTab`** on close — validation can **move the UI tab** away from where automation expects. **`fancyWarningOnClose`** can redirect via **`SECURITY.changeLocationHref("indexcitizen.htm")`**.
- **`xssfilter.js`**: On **`change`** for text inputs/textarea, values containing **`<` or `>`** trigger **`fancyAlertWithClear`** (field cleared on dismiss).
- **`security-util.js`**: CSRF-style **`appendToken`** on forms/links; automation must run against a **live** page so tokens match the server.
- **`hideandshow.js`**: **`hide()` / `show()`** toggle family-member divs (`hidediv` / `hidediv12`); consistent with **`#rbno`** “no family” path in **`FormFiller._fill_family_member_tab`**.
