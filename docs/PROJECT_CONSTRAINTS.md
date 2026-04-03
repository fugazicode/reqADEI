# Project Constraints Reference

**Purpose:** This file is the single authoritative reference for every project-specific, portal-specific, and FSM architecture constraint governing this codebase. Every plan and implementation must be validated against this file before execution. Update this file whenever a new constraint is confirmed.

**Sources:** Confirmed portal behaviour (`docs/portal_field_mapping (1).md`), runtime-verified debug session findings, and explicitly confirmed requirements from audit sessions.

---

## Section 1 — Portal Submission Constraints

### 1.1 Dropdown values are case-sensitive and exact

All portal dropdown selections must use the label exactly as it appears in the portal HTML. The `_select_by_label()` method in `form_filler.py` performs a string-exact match against the DOM option text.

| Enum | Correct value | Wrong value |
|---|---|---|
| Tenancy purpose | `"Residential"` | `"RESIDENTIAL"` |
| Tenancy purpose | `"commercial"` | `"Commercial"` |
| Address doc type | `"Aadhar Card"` | `"Aadhaar"` / `"Aadhaar Card"` |
| Relation type | `"Father"` | `"FATHER"` |

All normalisation from user input to portal-exact labels must go through the appropriate `OptionSet.normalize()` method in `shared/portal_enums.py`.

### 1.2 Indian state values must be UPPERCASE

`STATE_VALUES` in `form_filler.py` uses UPPERCASE keys (`"DELHI"`, `"UTTAR PRADESH"`, etc.). The lookup is `STATE_VALUES.get(value.upper())`. The `STATES` OptionSet in `shared/portal_enums.py` also uses UPPERCASE as its canonical form. Any state value written to the session must be UPPERCASE before it is presented to the user or submitted.

OCR-extracted state values are normalised to UPPERCASE in `core/pipeline_stages.py` immediately after the parsed values are written to the session, using `STATES.normalize(raw).upper()`.

### 1.3 District and police station coverage is Delhi-only

`DISTRICT_VALUES` and `POLICE_STATION_VALUES` in `form_filler.py` only contain the 16 Delhi districts and their stations. If a session payload contains a district or police station from any state other than Delhi, `form_filler.py` will log a warning and silently skip the selection. The portal will then block submission because the required dropdown is unset. This is a pre-existing architectural constraint — see Section 5 for the gap detail.

### 1.4 Owner address country and state must never be written

The portal pre-selects `INDIA` (value `80`) for country and `DELHI` (value `8`) for state on the Owner Information tab. Programmatically changing either field triggers the `checkForOtherCountry()` JavaScript handler, which clears all downstream district and police station dropdown options. `form_filler.py` intentionally leaves both fields untouched. No future change may add `ownerCountry` or `ownerState` writing to `_fill_owner_tab()`.

### 1.5 Tenanted premises address is always India/Delhi

The portal physically locks the Tenanted Premises Address country to `INDIA` and state to `DELHI` using single-entry dropdowns. `address_collection/handlers.py` sets `addr.state = "DELHI"` and `addr.country = "INDIA"` unconditionally. These two fields must never be made user-editable in the FSM overview and must never be included in the tenanted address field list in `labels.py`.

### 1.6 State selection triggers AJAX — district must be awaited

Selecting a state on the portal fires an XHR to `getdistricts.htm` to populate the district dropdown. `form_filler.py` uses `page.expect_response(lambda r: "getdistricts" in r.url)` to wait for this response before proceeding to select the district. Any code that selects a state must follow this await pattern; selecting the district immediately after `js_select` without waiting will find an empty dropdown.

### 1.7 Foreign address sentinels for non-India country

When a country other than India is selected, the portal accepts the following sentinel values in place of real dropdown selections:

| Field | DOM name | Sentinel value | Portal label |
|---|---|---|---|
| State | `tenantPermanentState` / `tenantPreviousState` | `99` | `---Not applicable---` |
| District | `tenantPermanentDistrict` / `tenantPreviousDistrict` | `99999` | `---Not applicable---` |
| Police Station | `tenantPermanentPoliceStation` / `tenantPreviousPoliceStation` | `99999999` | `---Not applicable---` |

These sentinels must be written directly to the DOM via JS when country is non-India. This path is not currently implemented — see Section 5.

### 1.8 Submission pre-validation fields

`_validate_required_fields_before_submit()` in `form_filler.py` checks the following fields before clicking `#submit123`. A value of `""`, `"-1"`, or `"0"` in any select field counts as not filled and raises `SubmissionValidationError`:

- `ownerFirstName`, `ownerLastName`
- `tenantFirstName`, `tenantLastName`
- `ownerOccupation` (select)
- `tenantAddressDocuments` (select)
- `tenancypurpose` (select)

---

## Section 2 — Mandatory Field Rules (FSM and Portal)

### 2.1 Exactly 5 mandatory fields per address section

Every address section in the FSM enforces exactly these 5 fields as mandatory. No other address field is mandatory. This rule is final and applies to all three address sections (owner, tenanted premises, tenant permanent).

1. `village_town_city`
2. `country`
3. `state`
4. `district`
5. `police_station`

This rule is enforced in two layers:
- **Runtime validation** — `form_payload.py`: `is_submittable()`, `owner_missing_mandatory()`, `tenanted_addr_missing_mandatory()`, `tenant_perm_addr_missing_mandatory()`
- **Overview display** — `labels.py`: `OWNER_MANDATORY`, `TENANTED_ADDR_MANDATORY`, `PERM_ADDR_MANDATORY`

Both layers must be kept in sync. Any change to mandatory fields must update both.

### 2.2 village_town_city is always mandatory regardless of country

Even for foreign addresses (country ≠ India), `village_town_city` must be filled. The portal enforces this field across all address sections. Fill the city name for foreign addresses (e.g. `"DUBAI"`, `"LONDON"`).

### 2.3 Mandatory validation must be unconditional

`form_payload.py` must not apply country-conditional guards (`if country == "INDIA"`) on `state`, `district`, or `police_station` for any address section. All 5 mandatory fields are always required. The India-conditional guard that previously existed in `tenant_perm_addr_missing_mandatory()` has been removed.

### 2.4 Tenanted premises auto-satisfies country and state

For the tenanted premises address, `country="INDIA"` and `state="DELHI"` are set automatically by `address_collection/handlers.py`. These fields are never shown to the user, never editble, and are considered permanently satisfied. They must not appear in `TENANTED_ADDR_FIELDS` in `labels.py`.

### 2.5 Owner country is auto-set; owner state is OCR-extracted

`pipeline_stages.py` automatically sets `owner.address.country = "INDIA"` after a successful OCR parse. `owner.address.state` is extracted from the Aadhaar card image and immediately normalised to UPPERCASE. If OCR misses the state, the user will see ⚠️ on the owner overview and must fill it via the state picker.

### 2.6 Non-mandatory address fields (reference)

The following address fields are optional and must not be marked mandatory in any validation code or overview:

`house_no`, `street_name`, `colony_locality_area`, `tehsil_block_mandal`, `pincode`

---

## Section 3 — FSM Architecture Constraints

### 3.1 Each picker flow must have its own FSM state

FSM states for picker flows must not be shared between sections. The following `ReviewStates` picker states are each dedicated to a single section:

| State | Section | Purpose |
|---|---|---|
| `PICKING_OWNER_DROPDOWN` | owner | Occupation, relation type, state |
| `PICKING_TENANT_DROPDOWN` | tenant | Occupation, relation type, doc type, tenancy purpose |
| `PICKING_PERM_DROPDOWN` | perm_addr | State |
| `PICKING_TENANTED_DISTRICT` | tenanted_addr | District selection |
| `PICKING_TENANTED_STATION` | tenanted_addr | Station selection |
| `PICKING_PERM_DISTRICT` | perm_addr | District selection |
| `PICKING_PERM_STATION` | perm_addr | Station selection |

The owner section must never borrow `PICKING_TENANTED_DISTRICT` or `PICKING_TENANTED_STATION`. A dedicated owner district/station picker state does not yet exist — if owner district/station editing is refactored, new states must be added.

### 3.2 All portal dropdown enums belong in portal_enums.py

Any enum that the FSM needs to present as a picker must be defined as an `OptionSet` in `shared/portal_enums.py`. Portal-specific value-to-ID lookup tables (`STATE_VALUES`, `DISTRICT_VALUES`, `POLICE_STATION_VALUES`) belong in `form_filler.py` only if they are used exclusively during submission. If the FSM needs to present options from one of these tables, promote it to an `OptionSet` in `portal_enums.py`.

Current enums in `portal_enums.py`:

| Name | Used for |
|---|---|
| `OCCUPATIONS` | Owner and tenant occupation picker |
| `STATES` | Owner state and tenant permanent address state picker |
| `TENANCY_PURPOSES` | Tenant tenancy purpose picker |
| `ADDRESS_DOC_TYPES` | Tenant ID proof type picker |
| `RELATION_TYPES` | Owner and tenant relation type picker |

### 3.3 Field order in labels.py determines callback indices

`_SECTION_FIELD_KEYS` in `features/data_verification/handlers.py` is derived from `list(OWNER_FIELDS.keys())` (and analogously for other section dicts) at import time. The `field_selector_keyboard()` in `keyboards.py` emits zero-based numeric indices as `callback_data` instead of full dot-paths to stay within Telegram's 64-byte limit. Inserting or reordering entries in any `*_FIELDS` dict in `labels.py` automatically adjusts the indices — there is nothing else to update. New fields must be placed in the correct display order within the dict.

### 3.4 callback_data must not exceed 64 bytes

Telegram enforces a 64-byte hard limit on `callback_data`. The following patterns are used to stay within this limit:

- Field selector keyboards use numeric indices (`edit_field:{section}:{index}`), not full dot-paths.
- `picker:small:{section}:{field_path}:{value}` — verify byte length for any new field path or option value combination. The longest current payload is approximately 61 bytes.
- `picker:station:{section}:{district}:{station}` — district and station names are short by convention (all uppercase, no special characters).

When adding new `picker:small:` or `picker:station:` payloads, count bytes explicitly: `len(f"picker:small:{section}:{field_path}:{value}".encode())`.

### 3.5 STATES alias dict must cover common OCR abbreviations

The `STATES` OptionSet aliases in `shared/portal_enums.py` must include common OCR abbreviations and misspellings that appear on Aadhaar cards (e.g. `"UP"` → `"UTTAR PRADESH"`, `"MP"` → `"MADHYA PRADESH"`, `"ORISSA"` → `"ODISHA"`, `"TELENGANA"` → `"TELANGANA"`). The full alias list is maintained in `shared/portal_enums.py`. When adding support for a new OCR source, verify its state output format and add aliases if needed.

### 3.6 Session model properties for image records

`session.owner_image_file_ids` and `session.tenant_image_file_ids` in `shared/models/session.py` are property setters that append to `session.image_records`. They do not replace existing records — they only add file IDs that are not already present. The pipeline (`core/pipeline_stages.py`) reads from `session.image_records` exclusively. Do not access raw file IDs outside the session model.

---

## Section 4 — Telegram UX Constraints

### 4.1 Inline keyboard button label maximum: 33 characters

Telegram inline keyboard buttons on small devices (~320–375 px) clip or wrap text beyond approximately 33 characters. This ceiling was measured against the shortest unambiguous existing label. All button labels must be ≤ 33 characters including any emoji prefix.

When proposing a new button label, count characters explicitly. Use abbreviations:

| Full form | Abbreviation |
|---|---|
| `Address` | `Addr` |
| `Permanent` | `Perm.` |
| `Identity` | `ID` |
| `Upload` | (drop entirely) |

### 4.2 Confirm button labels must match actual next FSM state

`_CONFIRM_LABELS` in `features/data_verification/keyboards.py` must accurately describe the state the user will land in after pressing the button. Whenever a confirm handler's `set_state()` call is changed, the corresponding label in `_CONFIRM_LABELS` must also be updated, and vice versa. Cross-reference the two files on every change.

Current correct labels:

| Section key | Label | Actual next state |
|---|---|---|
| `owner` | `"✅ Confirm Owner → Tenanted Addr"` | `AddressStates.ENTERING_TENANTED_ADDRESS` |
| `tenant` | `"✅ Confirm Tenant → Perm. Address"` | `ReviewStates.REVIEWING_PERM_ADDR` |
| `tenanted_addr` | `"✅ Confirm Address → Tenant ID"` | `IdentityStates.UPLOADING_TENANT_ID` |
| `perm_addr` | `"✅ Confirm & Submit"` | `SubmissionStates.SUBMITTING` |

### 4.3 Picker "Back" buttons navigate to overview, not field selector

All picker keyboards (`small_dropdown_keyboard`, `occupation_quick_keyboard`, `district_picker_keyboard`, `station_picker_keyboard`) use `"← Back"` with `callback_data=f"overview:back:{section}"`. This routes to the `overview_back` handler which restores the review state and refreshes the overview message. It does not return to the field selector list. This is intentional architecture. If a future change requires "back to field selector" navigation from within a picker, a new callback route and handler are required.

### 4.4 Multi-photo upload advertises accumulation but removes all-or-nothing

The upload confirm keyboard shows an accumulating count of uploaded photos. The "Remove" button (`upload:remove:{person}`) clears all images for that person at once. There is no per-image remove. This is a known UX limitation (U-8 from audit) — if per-image management is added, the `ImageRecord` model and the remove handler must both be updated.

---

## Section 5 — Known Gaps and Pre-existing Risks

These are confirmed gaps in the current implementation. Do not assume they work. Any plan that touches these areas must explicitly address the gap or explicitly accept the limitation.

### 5.1 Non-India country path not implemented for tenant permanent/previous address

`form_filler.py` `_fill_tenant_address_permanent()` has no branch for when `tenant.address.country` is non-India. The correct behaviour is to write sentinel values directly to the DOM (State=`99`, District=`99999`, Police Station=`99999999`). Until this is implemented, any tenant with a foreign permanent address will cause a submission failure.

**Impact:** High. **Status:** Not implemented.

### 5.2 Non-Delhi Indian state addresses will silently fail submission

`DISTRICT_VALUES` and `POLICE_STATION_VALUES` in `form_filler.py` only contain Delhi entries. If a tenant permanent address has an Indian state other than Delhi (e.g. Maharashtra), the district and police station AJAX selections will find no matching value, log a warning, and leave those dropdowns unset. The portal will block submission.

**Impact:** High. **Status:** Pre-existing risk, not introduced by recent changes.

### 5.3 Tenant previous address is not filled

`form_filler.py` only fills the Permanent Address sub-tab. The portal requires at least one of Previous or Permanent address to be filled. If Permanent address data is absent from the session, submission will fail regardless of whether Previous address data exists.

**Impact:** High. **Status:** Not implemented.

### 5.4 Owner address non-India/non-Delhi path does not exist

`form_filler.py` leaves owner Country and State at portal defaults (India/Delhi). An owner whose actual permanent address is outside Delhi will have the correct city, district, and police station in their Aadhaar card, but the portal will only allow Delhi district and station selections due to the hardcoded state. This will silently submit wrong address data.

**Impact:** High. **Status:** Pre-existing architectural limitation.

### 5.5 Session is not cleared after submission

After `trigger_submission` enqueues the job, the FSM state is set to `SubmissionStates.SUBMITTING` and remains there indefinitely. No end-of-flow message, no session cleanup, no `/start` prompt is shown. Any message sent by the user after submission goes unhandled. This is audit gap U-10.

**Impact:** Medium. **Status:** Known gap, not yet fixed.

### 5.6 No per-section mandatory field validation before advancing

The intermediate confirm handlers (`confirm_owner`, `confirm_tenant`, `confirm_tenanted_addr`) advance to the next section without checking whether the current section's mandatory fields are filled. Only `confirm_perm_addr_and_submit` validates all fields. A user can complete the entire flow with empty mandatory fields and only be blocked at the final submit step. This is audit gap L-7.

**Impact:** High. **Status:** Known gap, not yet fixed.

### 5.7 /start silently destroys an in-progress session

`cmd_start` in `identity_collection/handlers.py` unconditionally overwrites any existing session with a new `FormSession`. A user who accidentally sends `/start` mid-flow loses all in-progress data with no warning or confirmation prompt. This is audit gap L-5.

**Impact:** High. **Status:** Known gap, not yet fixed.

### 5.8 Pipeline error leaves upload UI in a dead state

When the image extraction pipeline returns an error (`session.last_error` is set), the confirm keyboard is deleted and the error is displayed, but no new keyboard or re-upload prompt is shown. The FSM state remains `UPLOADING_OWNER_ID` (correct), so a new photo will be accepted, but the user has no visible affordance to act. This is audit gap L-4.

**Impact:** High. **Status:** Known gap, not yet fixed.

### 5.9 Owner section borrows tenanted-address picker states for district/station

The owner address district picker currently uses `PICKING_TENANTED_DISTRICT` and `PICKING_TENANTED_STATION` states (see `edit_field_selected` in `handlers.py`). There are no dedicated `PICKING_OWNER_DISTRICT` or `PICKING_OWNER_STATION` states in `ReviewStates`. This is a logic inconsistency that does not cause runtime errors only because both sections cannot be in edit mode simultaneously. This is audit gap L-2.

**Impact:** Medium. **Status:** Known gap, not yet fixed.

---

## Revision History

| Date | Change | Session reference |
|---|---|---|
| 2026-04-03 | Initial creation. Captured constraints from audit, Problem 1 (address mandatory fields), Problem 1 follow-up (state picker/STATES enum), and Problem 2 (confirm button labels). | [FSM audit + fixes](8472e2dc-63a1-459d-9c47-3d514c1545f8) |
