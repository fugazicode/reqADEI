# Known Issues

**Last updated:** 2026-04-04  
**Purpose:** Track every confirmed bug, gap, or structural flaw. Update status when something is fixed. Do not delete rows — change the status instead.

---

## Priority levels

- 🔴 **Critical** — blocks submission or corrupts data for all or most users
- 🟠 **High** — blocks a significant group of users or causes silent wrong data
- 🟡 **Medium** — degrades experience but does not block submission
- 🟢 **Low** — cosmetic or structural, no user impact

## Status values

- `OPEN` — not yet addressed
- `IN PROGRESS` — being worked on
- `RESOLVED` — fixed; note the date
- `ACCEPTED` — known limitation, accepted for now

---

## Critical Issues 🔴

### Issue #1 — Tenant Aadhaar scan is never uploaded to the portal
**Where:** `core/pipeline_stages.py` (`ImageParsingStage`), `features/submission/handlers.py` → `trigger_submission()`
**What happened (historical):** Image bytes were discarded after OCR; submission used empty `image_bytes`.
**Resolution:** First downloaded tenant image bytes are stored on `session.tenant_image_bytes` after OCR download; `trigger_submission()` passes them into `SubmissionInput`. Document tab navigation targets `#fileField2` per `portal_field_mapping.md` §2B (live portal smoke test still recommended).
**Status:** `RESOLVED` (2026-04-04)

### Issue #A — Tenant ID proof type picker buttons all exceed Telegram's 64-byte limit
**Where:** `features/data_verification/keyboards.py` → `small_dropdown_keyboard()`, `features/data_verification/handlers.py` → `small_dropdown_selected()`
**What happened (historical):** Callback data embedded the full dot-path; `ADDRESS_DOC_TYPES` options exceeded 64 bytes.
**Resolution:** Callback pattern is `picker:small:{section}:{field_idx}:{opt}`; `field_idx` indexes `_SECTION_FIELD_KEYS[section]`; handler decodes index back to `field_path`.
**Status:** `RESOLVED` (2026-04-04)

---

## High Priority Issues 🟠

### Issue #2 — No validation before advancing past each review section
**Where:** `features/data_verification/handlers.py` → `confirm_owner()`, `confirm_tenant()`, `confirm_tenanted_addr()`
**What happens:** `confirm_owner()` and `confirm_tenanted_addr()` call `owner_missing_mandatory()` / `tenanted_addr_missing_mandatory()` and block with a field list when incomplete. `confirm_tenant()` still advances without a tenant-personal section guard; missing tenant fields are only caught at final submit.
**Fix (remaining):** Add `tenant_personal_missing_mandatory()` check to `confirm_tenant()` before transitioning.
**Status:** `OPEN`

### Issue #B — Foreign permanent address creates an unresolvable deadlock
**Where:** `features/data_verification/handlers.py` + `labels.py` + `form_filler.py`
**What happens:** A tenant with a non-India permanent address cannot fill state, district, or police station (the pickers only show Indian options). But these fields are marked mandatory and block submission. The user is permanently stuck.
**Fix:** Implement the "Not Applicable" sentinel path for non-India addresses in both the FSM (allow skipping state/district/station when country is non-India) and the form filler (write sentinel values to the portal DOM).
**Status:** `OPEN`

### Issue #C — Re-uploading after a failed extraction accumulates stale images
**Where:** `shared/models/session.py`, `features/identity_collection/handlers.py`
**What happened (historical):** Append-only setters let failed and retried images accumulate for OCR.
**Resolution:** Setters append with dedup so multiple photos per confirm still work; on pipeline error, `owner_upload_confirmed` / `tenant_upload_confirmed` clear `image_records` for that person before returning. Remove handlers still clear explicitly.
**Status:** `RESOLVED` (2026-04-04)

### Issue #D — Bot goes silent after submission with no next step
**Where:** `features/data_verification/handlers.py`, `features/submission/submission_worker.py`
**What happened (historical):** FSM stayed in `SUBMITTING` with no catch-all message handler.
**Resolution:** `confirm_perm_addr_and_submit()` sets `SubmissionStates.DONE`; `@router.message(SubmissionStates.DONE)` prompts for `/start`; worker sends PDF (or failure text) plus "Send /start to register another tenant."
**Status:** `RESOLVED` (2026-04-04)

### Issue #E — Pipeline error leaves the upload screen with no buttons
**Where:** `features/identity_collection/handlers.py` → `owner_upload_confirmed()` and `tenant_upload_confirmed()` error branch
**What happened (historical):** Error text gave no hint that another photo was accepted.
**Resolution:** Error message appends plain-text instruction to send a new photo; FSM remains `UPLOADING_*`.
**Status:** `RESOLVED` (2026-04-04)

### Issue #F — "South Delhi" OCR output does not match any portal district key
**Where:** `core/pipeline_stages.py`
**What happened (historical):** District string from OCR was written verbatim; aliases like `SOUTH DELHI` did not map to `SOUTH`.
**Resolution:** `_normalise_delhi_district()` maps OCR/colloquial variants to `DISTRICT_VALUES` keys after state normalisation.
**Status:** `RESOLVED` (2026-04-04)

### Issue #G — Last name is treated as mandatory but the portal does not require it
**Where:** `features/submission/form_filler.py` → `_validate_required_fields_before_submit()`
**What happened (historical):** `ownerLastName` / `tenantLastName` were in `required_text_fields`.
**Resolution:** Removed from `required_text_fields`; only first names remain required as text.
**Status:** `RESOLVED` (2026-04-04)

---

## Medium Priority Issues 🟡

### Issue #3 — Overview refresh fails silently if the message was deleted
**Where:** `features/data_verification/handlers.py` → `_refresh_overview()`
**What happened (historical):** `edit_message_text` failures were swallowed.
**Resolution:** On exception, sends a new overview message, updates `session.overview_message_id`, persists session.
**Status:** `RESOLVED` (2026-04-04)

### Issue #4 — District name mismatch between data files
**Where:** `data/police_stations.json` vs `data/delhi_police_stations.json` and `DISTRICT_VALUES`
**What happens:** The legacy file stores `"SOUTH EAST"` (no hyphen); the primary file and `DISTRICT_VALUES` use `"SOUTH-EAST"` (with hyphen). Auto-suggest from the legacy file can write the wrong key to the session.
**Fix:** Normalise district names at read time, or remove the legacy file and replace its data with entries from the primary file.
**Status:** `OPEN`

### Issue #6 — Stale buttons from old messages can affect a new session
**Where:** `features/data_verification/handlers.py`
**What happened (historical):** Callbacks had no state awareness.
**Resolution:** Section confirm callbacks are registered under the correct `ReviewStates.REVIEWING_*`. `overview:edit`, `overview:back`, and `edit_field` enforce `_SECTION_EDIT_STATE_IDS` / `_OWNER_EDIT_STATE_IDS` (etc.) before acting.
**Status:** `RESOLVED` (2026-04-04)

### Issue #7 — `/start` mid-flow silently destroys an in-progress session
**Where:** `features/identity_collection/handlers.py` → `cmd_start()`
**What happened (historical):** `/start` always replaced the session.
**Resolution:** If consent was given and FSM is not idle, first `/start` warns; second `/start` within 60 seconds discards (`pending_discard_start_at` on `FormSession`).
**Status:** `RESOLVED` (2026-04-04)

### Issue #8 — No text message handler for `PICKING_PERM_DROPDOWN` state
**Where:** `features/data_verification/handlers.py`
**What happened (historical):** Typed text in perm-address state picker was ignored.
**Resolution:** Handler replies to use buttons and deletes the user message.
**Status:** `RESOLVED` (2026-04-04)

### Issue #9 — Owner permanent address state treated as mandatory though not submitted
**Where:** `shared/models/form_payload.py` → `owner_missing_mandatory()`, `features/data_verification/labels.py` → `OWNER_MANDATORY`
**What happened (historical):** `owner.address.state` was mandatory in bot checks while `CONSTRAINTS.md` §2.5 forbids writing it in the form filler.
**Resolution:** Removed from `owner_missing_mandatory()` and `OWNER_MANDATORY`; field remains in `OWNER_FIELDS` for display. Comments cite §2.5.
**Status:** `RESOLVED` (2026-04-04)

---

## Low Priority Issues 🟢

### Issue #5 — Owner district/station picker borrows tenanted-address FSM states
**Where:** `features/data_verification/states.py`, `features/data_verification/handlers.py`
**What happened (historical):** Owner district/station edits used `PICKING_TENANTED_*` states.
**Resolution:** `PICKING_OWNER_DISTRICT` and `PICKING_OWNER_STATION` added; owner edit routes use them.
**Status:** `RESOLVED` (2026-04-04)

### Issue #H — Police station label mismatch for IITF Pragati Maidan
**Where:** `data/delhi_police_stations.json` vs `POLICE_STATION_VALUES` in `form_filler.py`
**What happened (historical):** JSON key did not match filler/portal label.
**Resolution:** JSON key set to `IITF,Pragati Maidan` to match `POLICE_STATION_VALUES` / portal.
**Status:** `RESOLVED` (2026-04-04)

---

## Resolved Issues ✅

Summary of fixes shipped 2026-04-04: #1, #A, #C, #D, #E, #F, #G, #3, #5, #6, #7, #8, #9, #H.  
**Still OPEN:** #2 (partial — `confirm_tenant` unchecked), #4, #B.

---

## Revision history

| Date | Change |
|------|--------|
| 2026-04-04 | Initial creation. Consolidated from `audit.md` and `ISSUES_AND_RESOLUTIONS.md`. All issues carry forward as OPEN. |
| 2026-04-04 | Status sync with codebase: Phase 1/2 fixes marked RESOLVED; #2 narrowed to remaining `confirm_tenant` gap; #9 added; summary table updated. |
