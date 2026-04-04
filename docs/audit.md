# FSM Flow Audit Report

Below is a structured audit of every identified logic issue, written in plain terms with step-by-step explanation and clear expected outcome.

---

## Issue 1 — Tenant Aadhaar Image Is Never Sent to the Portal (Critical)

**Where:** `features/submission/handlers.py` → `trigger_submission()`

**What happens step by step:**
1. The bot downloads the tenant's Aadhaar photo during the pipeline run and uses it only for OCR text extraction.
2. After extraction, the raw image bytes are discarded — they are never stored on the session.
3. When the user taps "Confirm & Submit", `trigger_submission()` builds the job with `tenant_image_bytes = b""` (an explicit empty byte string, hardcoded on that line).
4. Inside `FormFiller._fill_document_upload()`, the first thing checked is `if not image_bytes:` — which is `True` — so the method logs a warning and immediately returns without uploading anything.
5. The portal submission completes with no document attached.

**Outcome:** The document upload step is permanently skipped for every single submission. The portal receives a form with no proof of identity attached, which will likely cause the application to be rejected or incomplete.

---

## Issue 2 — No Validation at Intermediate Confirm Steps

**Where:** `features/data_verification/handlers.py` → `confirm_owner()` and `confirm_tenanted_addr()`

**What happens step by step:**
1. After the owner Aadhaar is scanned, the owner overview is shown. The user can tap "Confirm Owner → Tenanted Addr" immediately, even if mandatory fields like `first_name`, `state`, `district`, or `police_station` are blank.
2. `confirm_owner()` performs no checks — it unconditionally transitions to `ENTERING_TENANTED_ADDRESS`.
3. The same is true for `confirm_tenanted_addr()` — it moves to `UPLOADING_TENANT_ID` regardless of whether `village_town_city`, `district`, or `police_station` are filled.
4. Mandatory validation only runs at the very last step (`confirm_perm_addr_and_submit`), where ALL sections' missing fields are reported together in a single list.

**Outcome:** A user can sail through all intermediate steps with empty mandatory fields and only find out at the final submit that they need to go back and fill in data across multiple sections — with no easy way to navigate back to the right section from the error message.

---

## Issue 3 — Overview Refresh Fails Silently, Leaving the User Stuck

**Where:** `features/data_verification/handlers.py` → `_refresh_overview()`

**What happens step by step:**
1. After any edit (free text, occupation pick, district/station pick), the bot tries to update the overview message in-place using `bot.edit_message_text(...)`.
2. If the overview message was manually deleted by the user, or if the Telegram API returns an error (e.g., "message to edit not found"), the `except Exception: pass` block silently swallows the error.
3. No new overview message is sent as a fallback.
4. The user is left looking at a chat with no overview and no buttons. The FSM state is correctly set, but there is nothing for the user to interact with.
5. The only recovery path is to type `/cancel` and then `/start` and begin again from scratch.

**Outcome:** Any user who deletes the overview message — intentionally or accidentally — permanently loses their progress and their session data with no explanation.

---

## Issue 4 — District Name Mismatch Between Data Files Causes Silent Form Failure

**Where:** `data/police_stations.json` (legacy) vs `data/delhi_police_stations.json` and `DISTRICT_VALUES` in `form_filler.py`

**What happens step by step:**
1. The legacy file `police_stations.json` stores the South-East district as `"SOUTH EAST"` (no hyphen).
2. The primary data file `delhi_police_stations.json` and `DISTRICT_VALUES` in `form_filler.py` both store it as `"SOUTH-EAST"` (with a hyphen).
3. The `StationLookup.suggest()` method reads from the legacy file and can return `"SOUTH EAST"` as a district name and save it to the session payload.
4. During portal submission, `form_filler.py` does `DISTRICT_VALUES.get("SOUTH EAST")` — which returns `None` because the key is `"SOUTH-EAST"`.
5. The `_select_district_and_station()` method logs a warning and skips the district and station selection entirely.

**Outcome:** For any South-East locality (Lajpat Nagar, Kalkaji, Shaheen Bagh, etc.) auto-suggested from the legacy file, the district and police station are silently left blank on the submitted portal form.

---

## Issue 5 — Owner District and Station Picking Reuses Tenant FSM States

**Where:** `features/data_verification/handlers.py` → `edit_field_selected()` and `district_selected()`

**What happens step by step:**
1. When a user edits the owner's district or police station, the code sets the FSM state to `ReviewStates.PICKING_TENANTED_DISTRICT` and `ReviewStates.PICKING_TENANTED_STATION`.
2. There are no dedicated states for `PICKING_OWNER_DISTRICT` or `PICKING_OWNER_STATION` in `ReviewStates`.
3. The correct section ("owner") is carried through the callback data string, so the data is saved to the right payload path — this is what prevents a data bug today.
4. However, `district_reselect()` maps "owner" to `PICKING_TENANTED_DISTRICT` only by coincidence (as the default fallback), not by explicit design.
5. If any future handler is added with an FSM state filter on `PICKING_TENANTED_DISTRICT`, it will accidentally intercept owner district selections too.

**Outcome:** Currently no functional data corruption, but the shared state creates a structural fragility. Any addition of state-guarded handlers for the tenanted address flow will inadvertently affect the owner editing flow and vice versa.

---

## Issue 6 — Picker and Navigation Callbacks Have No FSM State Guards

**Where:** `features/data_verification/handlers.py` — `overview_edit`, `overview_back`, `edit_field_selected`, `district_selected`, `station_selected`, `small_dropdown_selected`, `occupation_selected`

**What happens step by step:**
1. All of these callbacks are registered with only `F.data.startswith(...)` as their filter — no FSM state restriction.
2. If a user has an old overview or picker message from a previous session still visible in their chat, tapping any button on it will fire the corresponding handler.
3. The handler will attempt to read the user's current session, which by this point may be a fresh session (after `/start`) or in a completely different FSM state.
4. For example, tapping an old "Confirm Owner" button after starting a fresh session will call `confirm_owner()`, which will transition the fresh session from `AWAITING_CONSENT` to `ENTERING_TENANTED_ADDRESS` — skipping the entire identity upload phase.

**Outcome:** Stale messages in the chat act as live controls. A user can accidentally corrupt their current session or skip required steps by tapping an old button.

---

## Issue 7 — `/start` Mid-Flow Leaves Stale Active Buttons in Chat

**Where:** `features/identity_collection/handlers.py` → `cmd_start()`

**What happens step by step:**
1. When a user types `/start` while already in a flow, a brand-new `FormSession` is created and replaces the existing one in the store.
2. The FSM state is set to `AWAITING_CONSENT`.
3. All previously sent messages — overview panels, picker keyboards, confirm buttons — remain visible in the chat with their buttons still active.
4. Because of Issue 6 above (no FSM guards on callbacks), tapping any of those old buttons will execute their handlers and interact with the new, empty session.
5. For example, tapping an old "✅ Confirm & Submit" button on the previous session's perm address overview would attempt to submit an empty form, triggering the mandatory field error message.

**Outcome:** Users who restart mid-flow face a confusing chat full of interactive-looking buttons from their previous session that either produce error messages or silently corrupt the new session's data.

---

## Issue 8 — `PICKING_PERM_DROPDOWN` State Has No Text Message Handler

**Where:** `features/data_verification/handlers.py` — missing handler for `ReviewStates.PICKING_PERM_DROPDOWN`

**What happens step by step:**
1. When editing the **state** field in the permanent address section, the FSM transitions to `ReviewStates.PICKING_PERM_DROPDOWN` and shows a button-based picker.
2. `PICKING_OWNER_DROPDOWN` and `PICKING_TENANT_DROPDOWN` both have registered `@router.message(...)` handlers that process typed text as an occupation search query.
3. `PICKING_PERM_DROPDOWN` has no such handler registered.
4. If the user types any text while in this state (e.g., trying to type a state name or accidentally sending a message), the message is silently ignored by the router.
5. The user is left in `PICKING_PERM_DROPDOWN` with no feedback, and the only way out is to tap one of the buttons or send `/cancel`.

**Outcome:** The permanent address dropdown state is behaviourally inconsistent with the owner and tenant dropdown states. Users who type instead of tap receive no response and no error, which feels like the bot has frozen.

---

## Issue 9 — Owner Address `state` Field Is Required in UI but Ignored by Form Filler

**Where:** `features/submission/form_filler.py` → `_fill_owner_tab()` and `shared/models/form_payload.py` → `owner_missing_mandatory()`

**What happens step by step:**
1. `owner_missing_mandatory()` includes `owner.address.state` as a mandatory field — the bot will block submission if it is empty.
2. The user must therefore set the owner's state (e.g., "DELHI") via the overview edit flow before they can submit.
3. However, inside `_fill_owner_tab()`, the comment explicitly says: *"Country/state are pre-selected in static HTML (India/Delhi). Changing either triggers checkForOtherCountry and clears downstream selects. Leave them untouched."*
4. The form filler deliberately never writes to the owner state field on the portal.
5. The data the user was forced to enter has no effect on what gets submitted.

**Outcome:** The user is required to fill in the owner's state in the bot, but that value is silently discarded during submission. The portal always uses its own default (India/Delhi) for the owner state, which is actually correct behavior — but the mandatory check in the bot forces unnecessary user effort and creates a misleading experience.    


Good — this file adds significant context. Cross-referencing it against the codebase reveals several new issues not caught in the initial audit, and adds hard constraint violations to some that were already flagged. Here is the updated report, covering only what is new or materially changed.

---

## Cross-Reference Summary

Issues from the original audit that the constraints file **confirms as documented known gaps** (no new detail needed): Issues 2 (no per-section validation → Section 5.6), Issue 5 (owner borrows tenanted states → Section 5.9), Issue 3 (silent overview refresh failure → partially Section 5.5), Issue 7 (stale buttons → Section 5.7).

Everything below is either **new** or **elevated in severity** by the constraints file.

---

## New Issue A — Every Button in the Tenant ID Proof Type Picker Exceeds Telegram's 64-Byte Limit (Critical)

**Where:** `features/data_verification/keyboards.py` → `small_dropdown_keyboard()`, triggered from `edit_field_selected()` for `enum_key == "ADDRESS_DOC_TYPES"`

**Constraint violated:** Section 3.4 — `callback_data` must not exceed 64 bytes.

**What happens step by step:**

1. When the user taps "Edit a Field" on the tenant overview and selects "ID Proof Type", the code calls `small_dropdown_keyboard(section="tenant", field_path="tenant.address_verification_doc_type", options=ADDRESS_DOC_TYPES.values)`.
2. Each button is built with the pattern: `f"picker:small:{section}:{field_path}:{opt}"`.
3. The base string alone — `picker:small:tenant:tenant.address_verification_doc_type:` — is already **58 bytes** before the option value is appended.
4. Every single option value pushes it over 64 bytes:

| Option value | Total bytes |
|---|---|
| `Aadhar Card` | 69 ❌ |
| `Any Other` | 67 ❌ |
| `Arms License` | 70 ❌ |
| `Driving License` | 73 ❌ |
| `Electricity Bill` | 74 ❌ |
| `Income Tax (PAN) Card` | 79 ❌ |
| `Passport` | 66 ❌ |
| `Ration Card` | 69 ❌ |
| `Telephone Bill` | 72 ❌ |
| `Voter Card` | 68 ❌ |

5. When the bot attempts to send this keyboard, the Telegram API rejects the entire `sendMessage` call with a Bad Request error.
6. No picker is shown to the user. The `await callback.message.answer(...)` call raises an exception that is not caught, silently terminating the handler.

**Outcome:** A tenant user can never edit their ID proof type through the bot. The field remains whatever was OCR-extracted (or empty). If OCR extracted the wrong doc type, there is no recovery path short of `/cancel` and starting over.

---

## New Issue B — Foreign Permanent Address Creates an Unresolvable Mandatory-Field Deadlock (Critical)

**Where:** Interaction between `features/data_verification/handlers.py` → `confirm_perm_addr_and_submit()`, `features/data_verification/labels.py` → `PERM_ADDR_MANDATORY`, and `features/data_verification/keyboards.py` picker generation.

**Constraints involved:** Section 1.7 (foreign address sentinels not implemented), Section 2.1 (all 5 address fields always mandatory), Section 5.1 (known gap — non-India path not implemented).

**What happens step by step:**

1. A tenant whose Aadhaar lists an address outside India (e.g. a foreign national with an OCI Aadhaar) reaches the permanent address review screen.
2. `PERM_ADDR_MANDATORY` requires `state`, `district`, and `police_station` to be filled. These are marked ⚠️ in the overview.
3. The user taps "Edit a Field" → "State". The state picker shows `STATES.values` — which contains only 37 Indian states and union territories. There is no "Not Applicable" option and no foreign country path.
4. Even if the user picks an Indian state as a workaround, the district picker only contains Delhi districts. There is no route to a non-Delhi, non-India district.
5. The police station picker only contains Delhi stations. Same problem.
6. The user taps "✅ Confirm & Submit". `confirm_perm_addr_and_submit()` calls `tenant_perm_addr_missing_mandatory()`, which returns `["tenant.address.state", "tenant.address.district", "tenant.address.police_station"]`, and the flow is blocked.
7. The error message lists the missing fields, but the user has already discovered there is no way to fill them through available UI.

**Outcome:** Any tenant with a non-Indian permanent address is permanently unable to submit. They cannot fill the required fields (no UI support), and the mandatory check blocks submission without them. The session must be abandoned. This is not just a form-filler gap (Section 5.1 acknowledges that) — it is a full FSM deadlock at the data-collection layer.

---

## New Issue C — Re-Upload After Pipeline Failure Accumulates Stale Image Records

**Where:** `features/identity_collection/handlers.py` → `owner_photo_received()` and `owner_upload_confirmed()` (and the tenant equivalents).

**Constraint involved:** Section 3.6 — pipeline reads from `session.image_records` exclusively; property setters only append, they do not replace.

**What happens step by step:**

1. User uploads owner photo #1. `session.owner_image_file_ids = [file_id_1]` is called. The setter appends an `ImageRecord` for `file_id_1` to `session.image_records`.
2. User taps Confirm. The pipeline runs and returns an error (e.g. blurry image, invalid Aadhaar checksum).
3. The error message is shown. The FSM state remains `UPLOADING_OWNER_ID`. Crucially, no image records are removed.
4. User uploads a corrected photo #2. `session.owner_image_file_ids = [file_id_2]` is called. The setter checks: `file_id_2` is not in `existing` (which contains `file_id_1`), so it appends a second `ImageRecord`.
5. Now `session.image_records` has two owner records: the bad photo and the corrected photo.
6. The confirm keyboard is rebuilt: `count = len(session.owner_image_file_ids)` → shows "2 images received." The user never sent two photos intentionally.
7. User taps Confirm again. The pipeline calls `bot.download()` on **both** images and sends both to Groq for OCR. The bad image from attempt #1 is still being processed alongside the corrected one.
8. Groq may extract conflicting or incorrect data by combining information across the bad and good images.

**Outcome:** After every failed upload attempt, the count of images sent to OCR grows by one. The OCR result becomes increasingly unreliable because stale, rejected images are included in every subsequent pipeline run. The user sees a confusing "2 images" count when they only uploaded one correction.

---

## New Issue D — Post-Submission Dead End: No Session Cleanup, No User Affordance

**Where:** `features/submission/handlers.py` → `trigger_submission()` and `features/submission/states.py`.

**Constraint:** Section 5.5 explicitly documents this as known gap U-10 with "High" impact.

**What happens step by step:**

1. After all sections are confirmed, `confirm_perm_addr_and_submit()` sets FSM state to `SubmissionStates.SUBMITTING` and calls `trigger_submission()`.
2. `trigger_submission()` enqueues the job, sends "⏳ Your form has been queued…" and returns.
3. The FSM state permanently remains `SubmissionStates.SUBMITTING`. No handler exists for any message or callback in this state.
4. When the `SubmissionWorker` finishes (which may take several minutes, or may fail), it sends a PDF or an error message directly via `bot.send_document()` / `bot.send_message()` — but takes no FSM action and does not clean up the session.
5. If submission succeeds and the user wants to register another tenant, there is no prompt to do so. If they type `/start`, Issue 5.7 applies — their session (still in SUBMITTING state) is silently destroyed and a fresh one is created, but all the overview messages from the prior session remain interactive (Issue 6 from the original audit).
6. If submission fails permanently (e.g. portal outage), the user receives "❌ Submission failed." but is given no instruction. They cannot resubmit — there is no handler in `SUBMITTING` state that accepts a retry command, and `/start` destroys the payload they spent time building.
7. The session remains in `SessionStore` until the hourly cleanup loop removes it (24-hour TTL by default), consuming memory for every completed or failed submission.

**Outcome:** Every user who reaches submission — successful or not — ends up in a permanently unresponsive state with no clear path forward. There is no completion screen, no retry option, and no graceful restart prompt.

---

## New Issue E — Pipeline Error Leaves Upload Screen With No Interactive Affordance

**Where:** `features/identity_collection/handlers.py` → `owner_upload_confirmed()` error branch (lines after `if session.last_error:`), and the identical pattern in `tenant_upload_confirmed()`.

**Constraint:** Section 5.8 explicitly documents this as known gap L-4 with "High" impact.

**What happens step by step:**

1. User uploads an Aadhaar photo and taps Confirm.
2. The confirm keyboard message is deleted: `await callback.message.delete()`.
3. A status message "⏳ Extracting…" is shown.
4. The pipeline returns an error. The error branch executes:
   - `status_msg.edit_text(f"❌ {session.last_error}\n\nPlease re-upload the owner ID.")` — this sends the error text with **no reply markup** (no keyboard).
5. The FSM state is correctly still `UPLOADING_OWNER_ID`, so a new photo message would be accepted by `owner_photo_received()`.
6. However, the user's screen now shows only a plain error text message. There is no "Try Again" button, no re-upload prompt button, no visible affordance of any kind.
7. The only way a user discovers they can just send another photo is by intuiting it — the text says "re-upload" but shows no camera or upload button the way the initial instructions did.

**Outcome:** Non-technical users who encounter an OCR failure (common with low-quality photos) will see what looks like a dead end — a plain error message with no buttons. Many will reach for `/cancel` and lose their session, or simply abandon the bot, rather than realising they just need to send another photo.

---

## Elevated Issue — Owner `state` Mandatory Check Contradicts Documented Portal Constraint

**Where:** `shared/models/form_payload.py` → `owner_missing_mandatory()` and `features/data_verification/labels.py` → `OWNER_MANDATORY` and `OWNER_FIELDS`.

**Constraint violated:** Section 1.4 — *"No future change may add `ownerCountry` or `ownerState` writing to `_fill_owner_tab()`."* and the reasoning: writing these fields triggers `checkForOtherCountry()`, which clears all downstream selects.

**This is an elevation of Original Issue 9.** The constraints file makes the conflict **explicit and intentional on the form-filler side**, which means the mandatory check on the bot side is not just wasteful — it is in direct contradiction with a documented architectural constraint.

**What happens step by step:**

1. `owner_missing_mandatory()` lists `owner.address.state` as a mandatory field.
2. `OWNER_FIELDS` in `labels.py` includes it as an editable `DROPDOWN` field.
3. If OCR fails to extract the owner state (which happens when the state is not printed on the visible face of the Aadhaar), the overview shows ⚠️ and the user is blocked from confirming.
4. The user opens the state picker, selects their state, and proceeds.
5. During submission, `_fill_owner_tab()` deliberately never touches the state field. The value the user was forced to enter is discarded.
6. Worse: if the owner is genuinely from outside Delhi, their real state (e.g. "UTTAR PRADESH") would be correct data — but writing it to the portal would fire `checkForOtherCountry()`, invalidating the district and police station dropdowns. The form filler is right not to write it; the mandatory check is wrong to require it.

**Outcome:** The mandatory check on `owner.address.state` forces user effort that produces no benefit and could — if the constraint were ever relaxed — actively break the district/station selection. The field should be removed from `OWNER_MANDATORY` and `OWNER_FIELDS`, and the constraint file (Section 1.4) should be cited as the reason.


## Changed Files Analysis

First, let me identify exactly what changed between the two codebase versions.

**No Python source files changed.** Every `.py` file is byte-for-byte identical to the previous version. All issues from the prior two audits remain unfixed.

**What was actually added:**

| File | Type | Status |
|---|---|---|
| `data/snapshots/8611462607/manifest.json` | Updated test snapshot | Different payload data |
| `data/snapshots/8611462607/tenant_image.bin` | New empty binary | Added |
| `debug-1331cc.log` | New debug log | Evidence of real failure |
| `docs/archive/obsolete_fsm_dependency_map.md` | Archived planning doc | Describes non-existent architecture; do not use |
| `docs/PROJECT_CONSTRAINTS.md` | In-repo copy of constraints | Same content as uploaded file |
| `docs/portal_field_mapping.md` | Portal reference doc | Reveals new issues |

---

## New Issues Discovered From the Added Files

---

### New Issue F — OCR Reliably Extracts an Invalid District Name, Silently Failing All Malviya Nagar Submissions

**Where:** `debug-1331cc.log` — 12 consecutive log entries, all sessions.

**What happens step by step:**

1. The debug log shows every OCR run for the Malviya Nagar area extracting `district_value: "South Delhi"` from the Aadhaar card — across 12 separate pipeline runs with different images.
2. `pipeline_stages.py` writes this raw value directly to `owner.address.district` (and `tenant.address.district`). No validation or correction is applied to district values — only state values go through `STATES.normalize()`.
3. The user sees `"South Delhi"` on their owner overview. It reads like a valid area. They confirm it.
4. During submission, `form_filler.py` does `DISTRICT_VALUES.get("SOUTH DELHI")` → `None`. The method logs `"Unknown district 'SOUTH DELHI' — skipping"` and returns without setting any district or police station.
5. The portal receives a form with no district and no police station for the owner address. Submission fails at the portal's server-side validation.

**Why this matters beyond what was already known:** The debug log proves this is not a theoretical edge case. It is the consistent, repeatable OCR output for one of the most common Delhi residential areas. "South Delhi" is the colloquial geographic designation that appears on Aadhaar cards for that region, but it is not one of the 16 portal district values. Every Malviya Nagar, Hauz Khas, Greater Kailash, and similar South Delhi area Aadhaar card will produce this failure on every run.

**Outcome:** A large proportion of real submissions — specifically all owner-occupied properties in South Delhi — will always fail silently. The district normalization that exists for states (`STATES.normalize()`) has no equivalent for districts.

---

### New Issue G — Last Name Is Treated as Mandatory by Form Filler But Is Optional on the Portal

**Where:** `features/submission/form_filler.py` → `_validate_required_fields_before_submit()` cross-referenced against `docs/portal_field_mapping.md` → Tab 1.1 and Tab 2A.

**What happens step by step:**

1. `_validate_required_fields_before_submit()` includes both `ownerLastName` and `tenantLastName` in `required_text_fields` — it will raise `SubmissionValidationError` if either is empty.
2. The portal field mapping document explicitly marks both `ownerLastName` and `tenantLastName` as **"No"** (not mandatory). The portal accepts and submits forms without them.
3. The Aadhaar extraction prompt (`prompts/id_extraction.txt`) splits names into `first_name` and `last_name`. Many Indians — particularly from South India and many parts of North India — use single-name Aadhaar cards where only one name appears. OCR correctly returns `null` for `last_name` in these cases.
4. The pipeline writes `null` for `last_name`, the DOM field is empty, and the pre-submit validator raises `SubmissionValidationError: "Pre-submit validation failed. Missing/invalid required fields: Owner last name"`.
5. The submission is aborted. The bot sends `"❌ Submission failed."` to the user with no further explanation.

**Outcome:** Any user whose Aadhaar card has a single name — a significant proportion of the Indian population — is permanently unable to complete a submission. The portal would have accepted the form; the form filler wrongly prevents it. This is a direct contradiction between the portal field mapping documentation and the code.

---

### New Issue H — Station Name Mismatch Between Picker Data and Lookup Table for IITF Pragati Maidan

**Where:** `data/delhi_police_stations.json` vs `features/submission/form_filler.py` → `POLICE_STATION_VALUES`.

**What happens step by step:**

1. In `delhi_police_stations.json` (NEW DELHI district), the station is stored as `"IITF PRAGATI MAIDAN"` — all caps, no comma.
2. In `form_filler.py` `POLICE_STATION_VALUES`, the same station is stored as `"IITF,Pragati Maidan"` — mixed case, with a comma.
3. The bot's station picker calls `station_lookup.stations_for_district("NEW DELHI")`, which reads from `delhi_police_stations.json` and returns `"IITF PRAGATI MAIDAN"`.
4. The user picks this station. It is saved to the payload as `"IITF PRAGATI MAIDAN"`.
5. During submission, `form_filler.py` does `POLICE_STATION_VALUES.get("IITF PRAGATI MAIDAN".upper())` → `POLICE_STATION_VALUES.get("IITF PRAGATI MAIDAN")` → `None`. The key in the dict is `"IITF,Pragati Maidan"`, which does not match.
6. The code falls through to `_select_by_label(station_field, "IITF PRAGATI MAIDAN")`. The portal label is `"IITF,Pragati Maidan"` (per the portal field mapping doc). The label match also fails.
7. The station is silently left unset on the form.

**Outcome:** Any user registering a tenancy or owner address in the New Delhi district near Pragati Maidan will have their police station silently dropped from the submission. This station name mismatch exists because the JSON data file and the `POLICE_STATION_VALUES` dict were populated from different sources and never reconciled.

---

### New Issue I — The FSM Architecture Document Describes a System That Does Not Exist

**Where:** `docs/archive/obsolete_fsm_dependency_map.md` (archived; obsolete)

**What happens step by step:**

1. The document describes an FSM built around `session.confirmation_queue`, `ConfirmationFlow`, `ExtrasCollectionStates`, `confirm:{field_path}` callbacks, `features/data_verification/confirmation_flow.py`, and `features/extras_collection/handlers.py`.
2. None of these exist in the current codebase. The session model has no `confirmation_queue` or `next_stage` field. There is no `confirmation_flow.py`. There is no `extras_collection` module. The `ReviewStates` group has no `CONFIRMING_FIELD` state.
3. The document itself acknowledges a partial mismatch in its "Doc note": it notes that `CODEBASE.md` references `friction.py` and `confirm2` handlers which also do not exist.
4. A developer reading this document to understand how the FSM works, plan a new feature, or debug a bug will reach completely wrong conclusions about which states exist, how field editing works, how station pickers are triggered, and how the queue drains into submission.
5. The document's "Suggested manual test order" and failure scenarios all reference the old queue-based flow, not the current overview-and-confirm flow.

**Outcome:** This document was an active liability while it lived beside authoritative docs. **Cleanup (2026-04):** it was moved to `docs/archive/obsolete_fsm_dependency_map.md` and marked obsolete. Use `docs/PROJECT_CONSTRAINTS.md` and `docs/portal_field_mapping.md` as references.