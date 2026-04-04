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
**Where:** `features/submission/handlers.py` → `trigger_submission()`
**What happens:** The bot reads the tenant's Aadhaar photo to extract text, then throws the image away. When submitting to the portal, `image_bytes` is hardcoded as empty (`b""`). The document upload step is silently skipped for every single submission.
**Impact:** Every submission is missing the required ID document. Likely rejected by the portal.
**Fix:** Save the downloaded image bytes to `session.tenant_image_bytes` during the extraction pipeline, then pass them into `SubmissionInput` at submission time.
**Status:** `OPEN`

### Issue #A — Tenant ID proof type picker buttons all exceed Telegram's 64-byte limit
**Where:** `features/data_verification/keyboards.py` → `small_dropdown_keyboard()` for `ADDRESS_DOC_TYPES`
**What happens:** The callback data pattern `picker:small:tenant:tenant.address_verification_doc_type:{option}` is already 58 bytes before the option value. Every option pushes it over 64 bytes. Telegram rejects the keyboard entirely.
**Impact:** Users can never edit the tenant's ID proof type. If OCR extracted it wrong, there is no way to correct it.
**Fix:** Use a short numeric code for the field path in the callback, mapped back server-side. Same approach used for field selector buttons.
**Status:** `OPEN`

---

## High Priority Issues 🟠

### Issue #2 — No validation before advancing past each review section
**Where:** `features/data_verification/handlers.py` → `confirm_owner()`, `confirm_tenant()`, `confirm_tenanted_addr()`
**What happens:** Users can confirm each section even if mandatory fields are empty. All validation only runs at the final submit step, where all missing fields across all sections are listed together with no easy way to navigate back.
**Fix:** Run the section-specific missing-field check inside each confirm handler before advancing.
**Status:** `OPEN`

### Issue #B — Foreign permanent address creates an unresolvable deadlock
**Where:** `features/data_verification/handlers.py` + `labels.py` + `form_filler.py`
**What happens:** A tenant with a non-India permanent address cannot fill state, district, or police station (the pickers only show Indian options). But these fields are marked mandatory and block submission. The user is permanently stuck.
**Fix:** Implement the "Not Applicable" sentinel path for non-India addresses in both the FSM (allow skipping state/district/station when country is non-India) and the form filler (write sentinel values to the portal DOM).
**Status:** `OPEN`

### Issue #C — Re-uploading after a failed extraction accumulates stale images
**Where:** `features/identity_collection/handlers.py` → photo received handlers
**What happens:** The image record setter only appends, never replaces. After a failed extraction, uploading a new photo adds to the list. Both the bad and the new image are sent to OCR together on the next attempt.
**Fix:** On pipeline failure (or when the user taps Remove), clear all image records for that person before accepting a new upload.
**Status:** `OPEN`

### Issue #D — Bot goes silent after submission with no next step
**Where:** `features/submission/handlers.py`, `features/submission/states.py`
**What happens:** After queuing a submission, the FSM stays in `SUBMITTING` state forever. No success/failure message guides the user on what to do next. If submission fails, there is no retry path.
**Fix:** After the worker completes (success or failure), send a clear outcome message and prompt the user to send `/start` for a new application.
**Status:** `OPEN`

### Issue #E — Pipeline error leaves the upload screen with no buttons
**Where:** `features/identity_collection/handlers.py` → `owner_upload_confirmed()` and `tenant_upload_confirmed()` error branch
**What happens:** When extraction fails, the error message is shown as plain text with no keyboard. The FSM state is correct (still `UPLOADING_*`), so a new photo would be accepted — but the user has no visible way to know this.
**Fix:** After showing the error message, re-send the upload instructions and the confirm/remove keyboard.
**Status:** `OPEN`

### Issue #F — "South Delhi" OCR output does not match any portal district key
**Where:** `core/pipeline_stages.py` → state normalisation (no equivalent for district)
**What happens:** Aadhaar cards for Malviya Nagar, Hauz Khas, and similar South Delhi areas reliably extract as district = `"South Delhi"`. The portal key is `"SOUTH"`. There is no district normalisation step, so `DISTRICT_VALUES.get("SOUTH DELHI")` returns `None` and the district is silently left blank.
**Fix:** Add a district normalisation/alias step in `pipeline_stages.py`, similar to the existing `STATES.normalize()` call. Map `"SOUTH DELHI"` → `"SOUTH"`, and other common OCR variants.
**Status:** `OPEN`

### Issue #G — Last name is treated as mandatory but the portal does not require it
**Where:** `features/submission/form_filler.py` → `_validate_required_fields_before_submit()`
**What happens:** The pre-submit validator raises an error if owner or tenant last name is empty. Many Indian Aadhaar cards have a single name with no last name. These users can never submit.
**Fix:** Remove `ownerLastName` and `tenantLastName` from the required fields list. The portal accepts submissions without them.
**Status:** `OPEN`

---

## Medium Priority Issues 🟡

### Issue #3 — Overview refresh fails silently if the message was deleted
**Where:** `features/data_verification/handlers.py` → `_refresh_overview()`
**What happens:** If the user deletes the overview message, any attempt to update it raises an exception that is swallowed silently. The user is left with no overview and no buttons. Only `/cancel` + `/start` recovers.
**Fix:** On edit failure, send a new overview message and update `session.overview_message_id`.
**Status:** `OPEN`

### Issue #4 — District name mismatch between data files
**Where:** `data/police_stations.json` vs `data/delhi_police_stations.json` and `DISTRICT_VALUES`
**What happens:** The legacy file stores `"SOUTH EAST"` (no hyphen); the primary file and `DISTRICT_VALUES` use `"SOUTH-EAST"` (with hyphen). Auto-suggest from the legacy file can write the wrong key to the session.
**Fix:** Normalise district names at read time, or remove the legacy file and replace its data with entries from the primary file.
**Status:** `OPEN`

### Issue #6 — Stale buttons from old messages can affect a new session
**Where:** `features/data_verification/handlers.py` — all callback handlers lack FSM state filters
**What happens:** Tapping a button on an old overview message fires its callback handler regardless of the current FSM state. This can skip steps or corrupt a fresh session.
**Fix:** Add FSM state filters to critical callbacks, or embed a session generation token in callback data so stale buttons are ignored.
**Status:** `OPEN`

### Issue #7 — `/start` mid-flow silently destroys an in-progress session
**Where:** `features/identity_collection/handlers.py` → `cmd_start()`
**What happens:** Sending `/start` while filling a form overwrites the session with no warning. All progress is lost.
**Fix:** If a session with data already exists, prompt for confirmation before wiping it.
**Status:** `OPEN`

### Issue #8 — No text message handler for `PICKING_PERM_DROPDOWN` state
**Where:** `features/data_verification/handlers.py`
**What happens:** The owner and tenant dropdown states handle typed text as occupation search. The permanent address dropdown state has no handler, so typing anything is silently ignored.
**Fix:** Add a handler for `PICKING_PERM_DROPDOWN` that either mirrors the search behaviour (if applicable) or replies with a prompt to use the buttons.
**Status:** `OPEN`

---

## Low Priority Issues 🟢

### Issue #5 — Owner district/station picker borrows tenanted-address FSM states
**Where:** `features/data_verification/handlers.py` → `edit_field_selected()`, `district_selected()`
**What happens:** When editing the owner's district or police station, the FSM transitions to `PICKING_TENANTED_DISTRICT` / `PICKING_TENANTED_STATION`. The correct section is carried in callback data, so no data bug exists today. However, any future handler with a state filter on `PICKING_TENANTED_DISTRICT` will accidentally intercept owner edits too.
**Fix:** Add `PICKING_OWNER_DISTRICT` and `PICKING_OWNER_STATION` states to `ReviewStates` and route owner edits through them.
**Status:** `OPEN`

### Issue #H — Police station label mismatch for IITF Pragati Maidan
**Where:** `data/delhi_police_stations.json` vs `POLICE_STATION_VALUES` in `form_filler.py`
**What happens:** The JSON file stores `"IITF PRAGATI MAIDAN"` (all caps, no comma). The filler dict and the portal label both use `"IITF,Pragati Maidan"` (mixed case, comma). The picker saves the wrong format; the filler cannot match it.
**Fix:** Align `delhi_police_stations.json` station labels to exactly match the portal labels used in `POLICE_STATION_VALUES`.
**Status:** `OPEN`

---

## Resolved Issues ✅

_(None yet — add rows here as issues are fixed, with the fix date)_

---

## Revision history

| Date | Change |
|------|--------|
| 2026-04-04 | Initial creation. Consolidated from `audit.md` and `ISSUES_AND_RESOLUTIONS.md`. All issues carry forward as OPEN. |
