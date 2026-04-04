# OBSOLETE — DO NOT USE FOR CURRENT CODEBASE

This file was moved from `docs/` during documentation cleanup. It describes a **queue-based FSM and modules that do not exist** in the current app (e.g. `confirmation_flow.py`, `confirmation_queue`). For accurate architecture, use [`docs/CONSTRAINTS.md`](../CONSTRAINTS.md) and the real handlers under `features/data_verification/`.

---

# FSM: Data verification dependency map

Training artifact for planning and debugging the aiogram FSM around field confirmation. **No code** — text-only dependencies, transitions, and high-friction validation.

**Primary modules**

| Layer | Path | Role |
|--------|------|------|
| States | `features/data_verification/states.py` | `CONFIRMING_FIELD`, `AWAITING_EDIT_INPUT`, `PICKING_DISTRICT`, `PICKING_STATION` |
| Queue + prompts | `features/data_verification/confirmation_flow.py` | `ConfirmationFlow.build_queue`, `show_next_field` |
| Handlers + router | `features/data_verification/handlers.py` | Callbacks, `_next_step`, pickers |
| Session model | `shared/models/session.py` | `confirmation_queue`, `next_stage`, `current_editing_field`, `edit_return_state`, … |
| Entry into verification | `features/identity_collection/handlers.py` | After pipeline: `next_stage`, `build_queue`, first `show_next_field` |
| Tenanted address branch | `features/extras_collection/handlers.py` | Separate queue + `TENANTED_ADDRESS_CONFIRM` |

**Doc note:** `CODEBASE.md` mentions `confirm2:` and `HIGH_FRICTION_FIELDS` / `friction.py`. The current tree has **no** `friction.py` and **no** `confirm2` handler — confirmation is a **single** `confirm:{field_path}` that pops the queue head when it matches.

---

## 1. Confirm callback and queue progression (`map-confirm-loop`)

### 1.1 Preconditions

- `session.confirmation_queue` is non-empty (head = field awaiting confirm/edit UI).
- User taps **Confirm** on the active prompt (inline keyboard from `confirm_edit_keyboard`).

### 1.2 Trigger

- `CallbackQuery` with `data` prefix `confirm:` → handler `confirm_field` in `features/data_verification/handlers.py`.

### 1.3 Guards (stale interaction defense)

| Guard | Effect |
|--------|--------|
| No `callback.from_user` / message / data | Handler returns (no-op). |
| No session | Alert: session expired. |
| `field_path` from callback ≠ `confirmation_queue[0]` **or** queue empty | Alert: “This confirmation is no longer active.” **No pop.** |

This is the **queue integrity + stale callback** coupling: the callback must match the **current head** exactly.

### 1.4 Mutations (success path)

1. If head equals `field_path`, **`confirmation_queue.pop(0)`** once (second check is redundant with guard but keeps pop safe).
2. Delete prior prompt via `last_prompt_message_id`; clear that id.
3. `session_store.save(session)`.
4. `callback.answer("Confirmed")`.
5. **`_next_step(..., submission_worker)`** — worker needed only when queue drains with `next_stage == "submission"` and payload is submittable.

### 1.5 `_next_step` when queue still has items

- Instantiates `ConfirmationFlow(session)` and calls `show_next_field(message, state)`.
- Returns:
  - **`confirm`**: prompt with Confirm/Edit already sent; FSM stays whatever it was (typically `CONFIRMING_FIELD`).
  - **`missing`**: sets `edit_return_state` / `edit_return_person`, saves, sets **`AWAITING_EDIT_INPUT`**.
  - **`missing_picker`**: sets edit-return fields, then routes to district or station picker (`_start_district_picker` / `_start_station_picker`). **`station_lookup`** is only passed into `_next_step` from internal branches — **`confirm_field` does not pass `station_lookup`**, so for `missing_picker` on a station field, code may use the fallback branch (prompt district keyboard without lookup) inside `_next_step`.

### 1.6 Failure scenarios (planning / debug)

| # | Scenario | Expected symptom |
|---|-----------|-------------------|
| A | User taps Confirm on an **old** message after queue advanced | Pop rejected; alert “no longer active”. |
| B | Double pop | Guard + single `pop(0)` after match prevents double advance if logic is unchanged. |
| C | `confirm_field` → `_next_step` with empty district/station head and `missing_picker` for station | `station_lookup is None` → fallback forces district picker; verify UX matches intent. |

### 1.7 Validation evidence

- Queue head in session matches the keyboard’s `confirm:` payload.
- After confirm, next prompt matches **next** queue item or empty-queue branch fires.
- Telegram shows “Confirmed” toast only when pop succeeded.

---

## 2. Free-text edit path (`validate-edit-path`)

### 2.1 Entry: `edit:{field_path}`

**Handler:** `edit_field` (`handlers.py`).

| Step | Behavior |
|------|-----------|
| Session load | Expired → alert. |
| `current_editing_field = field_path` | |
| `edit_return_state = await state.get_state()` | **Saves FSM state at time of edit** (may be `CONFIRMING_FIELD` or `ExtrasCollectionStates.TENANTED_ADDRESS_CONFIRM`). |
| `edit_return_person = session.current_confirming_person` | |
| District field set | `PICKING_DISTRICT` + district keyboard (no free text). |
| Station field set | `_start_station_picker` (enforces district + `StationLookup`). |
| Else | `AWAITING_EDIT_INPUT` + text prompt. |

**Checklist — edit return integrity**

- `edit_return_state` captures **return target**; pickers clear it when returning to confirmation (`pick_district` / `pick_station` / `skip_station`).
- If `edit_return_state` were **None** after text edit, `receive_edit_input` falls back to `CONFIRMING_FIELD` and logs a warning.

### 2.2 Processing: text in `AWAITING_EDIT_INPUT`

**Handler:** `receive_edit_input`.

| Step | Behavior |
|------|-----------|
| Guards | user, text, session, `current_editing_field` present. |
| Aadhaar field | If path ends with `address_verification_doc_no`, `validate_aadhaar`; on failure re-prompt, **stay** in `AWAITING_EDIT_INPUT`. |
| Cleanup | Deletes previous prompt and **incoming** user message (`_cleanup_for_incoming_user_message`). |
| Payload | `PayloadAccessor.set(..., current_editing_field, value)`; `current_editing_field = None`. |
| Return | Clear `edit_return_state` / `edit_return_person`; `state.set_state(return_state)`; **`_next_step(..., submission_worker)`**. |

**Checklist — queue integrity on edit**

- Editing does **not** remove the head of `confirmation_queue` until the user later **confirms** that field (or the flow advances through missing-field handling). Text entry only fills payload.

**Checklist — prompt lifecycle**

- `_cleanup_for_incoming_user_message` clears `last_prompt_message_id` after delete; next `_next_step` / `show_next_field` sets a new prompt id.

### 2.3 Failure scenarios

| # | Scenario | Risk |
|---|----------|------|
| A | `edit_return_state` missing | Fallback to `CONFIRMING_FIELD` may be wrong if user was in `TENANTED_ADDRESS_CONFIRM`. |
| B | User edits field not matching queue head | Allowed by UI if keyboards are stale; confirm handler still rejects wrong-head confirm. |
| C | `receive_edit_input` calls `_next_step` without `station_lookup` | Same as confirm path: `missing_picker` for station uses fallback inside `_next_step`. |

---

## 3. District / station pickers (`validate-picker-paths`)

### 3.1 Field sets (duplicated concept)

- `handlers.py`: `_DISTRICT_FIELDS`, `_STATION_FIELDS`.
- `confirmation_flow.py`: same sets for `missing_picker` vs free-text `missing`.

**Coupling:** changing a path requires updating **both** files (high friction).

### 3.2 District picker

| Trigger | `PICKING_DISTRICT` + `pickdistrict:` / `pickdistrictpage:` |
|--------|-------------------------------------------------------------|
| Guard | `current_editing_field in _DISTRICT_FIELDS`; else “no longer active”. |
| Success | `PayloadAccessor.set(payload, target, district)`; clear prompt id. |
| Branch | If paired `police_station` empty → set `current_editing_field` to station path → `_start_station_picker`. Else clear `current_editing_field`, restore `edit_return_state` (or default `CONFIRMING_FIELD`), `_next_step` **without** `submission_worker`. |

**Pagination:** `pickdistrictpage:{n}` edits reply markup only.

### 3.3 Station picker

| Trigger | `_start_station_picker` sets `PICKING_STATION`; callbacks `pickstation:`, `pickstationpage:`, `pickstationskip:`. |
|--------|-------------------------------------------------------------|
| Preconditions | `current_editing_field in _STATION_FIELDS`. |
| District required | Reads `owner.address.district` or `tenant.tenanted_address.district`. If empty → message, repoint `current_editing_field` to district → `_start_district_picker`. |
| Station list | `station_lookup.stations_for_district(district)`; empty list → force district re-pick. |
| Success | Set station on payload; clear editing field; restore state; `_next_step`. |
| Skip | `pickstationskip:` — **does not** set station; clears editing; returns; may leave station empty (submission gate may fail later). |

**Checklist — picker coupling**

- Station list always derived from **current** district in payload (pagination recomputes in `station_page`).
- Stale picker: `target not in _STATION_FIELDS` / district set rejects with alert.

### 3.4 `ConfirmationFlow.show_next_field` for empty district/station

- Empty value + path in `_DISTRICT_FIELDS` or `_STATION_FIELDS` → **`missing_picker`**: deletes last prompt, sets `current_editing_field`, **does not** send a new message.

**Gap (entry from identity):** `owner_upload_done` / `tenant_upload_done` only handle `result == "missing"`, not **`missing_picker`**. If the **first** queue item is an empty district/station, the user may remain in `CONFIRMING_FIELD` with no new prompt until another action. **Operational tests should cover OCR leaving district/station empty at head.**

---

## 4. End-of-queue routing (`map-exit-routing`)

### 4.1 Who sets `next_stage`

| Event | `next_stage` value | Where |
|--------|-------------------|--------|
| Owner ID done | `"owner_extras"` | `identity_collection.handlers.owner_upload_done` |
| Tenant ID done | `"tenant_extras"` | `identityCollection.handlers.tenant_upload_done` |
| Tenanted address parsed | `"submission"` | `extras_collection.handlers.receive_tenanted_address` |

### 4.2 `_next_step` when `confirmation_queue` is empty

Order in `handlers.py` (approximate):

1. **`next_stage == "submission"`**
   - If `payload.is_submittable()`:
     - Build `SubmissionInput`, `submission_worker.enqueue`, `SubmissionStates.COMPLETE`, user message with queue position (or test message if worker `None`).
   - Else: “Some required fields are still missing.”
2. **`next_stage == "owner_extras"`**
   - Clear `next_stage`; `ExtrasCollectionStates.OWNER_OCCUPATION`; occupation keyboard.
3. **`next_stage == "tenant_extras"`**
   - Clear `next_stage`; `ExtrasCollectionStates.TENANT_EXTRAS`; purpose keyboard.
4. Else: save and return (idle edge case).

**Completion gate:** submission only when **`is_submittable()`** passes — aligns with checklist.

### 4.3 Tenanted address confirmation FSM

- After parse: `TENANTED_ADDRESS_CONFIRM` (extras state), **not** `DataVerificationStates.CONFIRMING_FIELD`.
- `edit:` / `confirm:` handlers have **no** `StateFilter` — they still run; `edit_return_state` may be `TENANTED_ADDRESS_CONFIRM.state`.
- Extras `pick_station` callback **mutates queue** (`remove` station field) when user pre-picks station — **different** from data-verification station picker semantics.

### 4.4 Failure scenarios

| # | Scenario | Outcome |
|---|----------|---------|
| A | Queue empty, `next_stage` wrong / `None` | Silent save + return — user may see no prompt. |
| B | `next_stage == "submission"` but payload incomplete | Message only; no enqueue. |
| C | `submission_worker` missing when calling `_next_step` from picker return | Submission branch not used until a code path passes worker; pickers call `_next_step` without worker (OK for mid-queue). |

### 4.5 Validation evidence

- After last confirm in owner tenant-ID queue: state → `OWNER_OCCUPATION` and `next_stage` cleared.
- After last confirm in tenanted address queue: enqueue message or missing-fields message from submission branch.

---

## Quick reference — session fields touched by verification FSM

| Field | Written by |
|--------|------------|
| `confirmation_queue` | `ConfirmationFlow.build_queue`, `confirm_field` pop, extras `pick_station` remove |
| `current_editing_field` | `show_next_field`, `edit_field`, pickers, `receive_edit_input` |
| `edit_return_state` / `edit_return_person` | `edit_field`, `_next_step` missing paths, identity/extras first missing, cleared on return |
| `last_prompt_message_id` | `_send_prompt`, `show_next_field`, deletions |
| `next_stage` | identity upload done, address receive, cleared in `_next_step` for extras transitions |

---

## Suggested manual test order (one functionality at a time)

1. Confirm through two fields — queue advances; stale second message rejected.
2. Edit middle field (free text) — value saved; return to same FSM parent; confirm advances.
3. Edit district — station auto-guided if empty; pagination on district/station keyboards.
4. Skip station — flow continues; verify `is_submittable()` later.
5. Full owner → extras → tenant → address → submission enqueue (or missing-field message).

This document satisfies the four plan todos without modifying the plan file.
