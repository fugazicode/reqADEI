# Constraints Reference

**Last updated:** 2026-04-04
**Purpose:** Every plan and code change must be validated against this file before execution. When a constraint is confirmed or updated, note the date and source.

---

## How to read this document

- **CONFIRMED** = verified against the live portal or through direct code testing.
- **ASSUMED** = not yet live-verified; treat as true until proven otherwise.
- **OPEN** = contradictory or unclear; do not act on this until resolved.

---

## Section 1 — Portal: Dropdowns and Values

### 1.1 Dropdown values are exact and case-sensitive
The portal matches dropdown options by their exact label text. A wrong case or spelling causes silent failure.

| Field | Correct value | Wrong value |
|-------|--------------|-------------|
| Tenancy purpose | `"Residential"` | `"RESIDENTIAL"` |
| Tenancy purpose | `"commercial"` | `"Commercial"` |
| Tenant ID proof type | `"Aadhar Card"` | `"Aadhaar Card"` |
| Relation type | `"Father"` | `"FATHER"` |

**Status:** CONFIRMED (live log capture)

### 1.2 Indian state values must be stored in UPPERCASE
The state lookup table (`STATE_VALUES` in `form_filler.py`) uses UPPERCASE keys. Any state value written to the session must be UPPERCASE before display or submission.

**Status:** CONFIRMED

### 1.3 District and police station data covers Delhi only
The district and police station dropdowns only contain entries for the 16 Delhi districts. Any address with an Indian state other than Delhi will silently fail at the district/station step.

**Status:** CONFIRMED — pre-existing architectural limit

---

## Section 2 — Portal: Address Rules

### 2.1 Tenanted premises address is always India / Delhi
The portal locks the tenanted premises country to `INDIA` and state to `DELHI` using single-option dropdowns. These two fields are set automatically by the bot and must never be shown to the user or made editable.

**Status:** CONFIRMED (live log capture)

### 2.2 All other address sections allow any country
Owner permanent address, tenant permanent address, and tenant previous address all accept any of the 216 countries in the portal dropdown.

**Status:** CONFIRMED

### 2.3 Village / Town / City is always required, regardless of country
Even for foreign addresses, this field must be filled with the city name (e.g. `"DUBAI"`, `"LONDON"`).

**Status:** CONFIRMED

### 2.4 Foreign country makes State, District, Police Station "Not Applicable"
When a non-India country is selected on any address section (other than tenanted premises), the portal accepts these sentinel values:

| Field | Sentinel value | Portal label |
|-------|---------------|-------------|
| State | `99` | `---Not applicable---` |
| District | `99999` | `---Not applicable---` |
| Police Station | `99999999` | `---Not applicable---` |

These must be written directly to the DOM when country is non-India. This is **not yet implemented** — see `ISSUES.md` Issue #B.

**Status:** CONFIRMED (portal behaviour); NOT IMPLEMENTED in code

### 2.5 Owner address country and state must not be changed by code
The portal pre-selects `INDIA` and `DELHI` for the owner address. Changing either field programmatically triggers a JavaScript handler that clears the district and police station dropdowns. The form filler deliberately leaves these untouched.

**Status:** CONFIRMED

### 2.6 Selecting a state triggers an AJAX call before district options load
After selecting a state, the portal fires a network request to load district options. Code must wait for this response before attempting to select a district.

**Status:** CONFIRMED

---

## Section 3 — Portal: Submission

### 3.1 Last name is NOT required by the portal
The portal accepts submissions without owner or tenant last name. The pre-submit validation in code incorrectly treats last name as required. This must be fixed — see `ISSUES.md` Issue #G.

**Status:** CONFIRMED (portal field mapping); code is WRONG

### 3.2 Fields the portal requires before submission
These fields must be non-empty before the submit button is clicked:

| Field | Type |
|-------|------|
| Owner first name | Text |
| Owner occupation | Dropdown |
| Tenant first name | Text |
| Tenant ID proof type | Dropdown |
| Tenant ID proof document number | Text |
| Purpose of tenancy | Dropdown |
| Tenant Aadhaar scan (file upload) | File |

**Status:** CONFIRMED

---

## Section 4 — Telegram: Button and Callback Limits

### 4.1 Button label maximum is 33 characters
Button text longer than ~33 characters clips on small screens. Use abbreviations: `Addr` not `Address`, `Perm.` not `Permanent`, `ID` not `Identity`.

**Status:** CONFIRMED

### 4.2 Callback data maximum is 64 bytes (UTF-8 encoded)
Every inline button's callback data must be 64 bytes or fewer. Use numeric indices in field selector buttons instead of full dot-paths. Verify byte length explicitly when adding new picker buttons:

```python
len(f"picker:small:{section}:{field_path}:{value}".encode("utf-8")) <= 64
```

The current tenant ID proof type picker **violates this rule** — all buttons exceed 64 bytes. See `ISSUES.md` Issue #A.

**Status:** CONFIRMED violation exists

---

## Section 5 — FSM Architecture

### 5.1 Each picker flow must have its own dedicated FSM state
Picker states must not be shared between sections. The owner district/station picker currently borrows tenanted-address states — this is a known structural flaw (Issue #5) that does not currently cause data bugs but will if state-guarded handlers are added.

### 5.2 All portal dropdown options must be defined in `portal_enums.py`
Any value that the FSM needs to present as a picker must be defined as an `OptionSet` in `shared/portal_enums.py`. Portal-specific lookup tables (`STATE_VALUES`, `DISTRICT_VALUES`, `POLICE_STATION_VALUES`) stay in `form_filler.py`.

### 5.3 Field order in `labels.py` determines button callback indices
The field selector keyboard uses numeric indices (not field paths) as callback data. Adding or reordering fields in any `*_FIELDS` dict in `labels.py` automatically changes all indices — no other file needs updating, but the order must be intentional.

### 5.4 Owner occupation defaults to "SERVICE" if OCR does not extract it
After a successful owner image parse, if occupation is null, it is automatically set to `"SERVICE"`. This is a silent default and the user can change it on the review screen.

**Status:** CONFIRMED (code behaviour)

---

## Section 6 — Known Gaps (do not assume these work)

These are confirmed gaps. Any plan touching these areas must explicitly address the gap or document acceptance of the limitation.

| Gap | Impact | Issue ref |
|-----|--------|-----------|
| Tenant Aadhaar scan is never uploaded to the portal | **Critical** | #1 |
| Tenant ID proof type picker buttons all exceed 64 bytes | **Critical** | #A |
| Foreign permanent address creates an unresolvable deadlock | **High** | #B |
| Non-India country path not implemented in form filler | **High** | Issue #B, §2.4 |
| Non-Delhi Indian state addresses will silently fail submission | **High** | inherited |
| Tenant previous address is never filled | **High** | #5.3 |
| Last name treated as mandatory by filler but optional on portal | **High** | #G |
| "South Delhi" OCR district output does not match any portal key | **High** | #F |

---

## Revision history

| Date | Change |
|------|--------|
| 2026-04-04 | Created from `PROJECT_CONSTRAINTS.md` + contradiction resolution from `ISSUES_AND_RESOLUTIONS.md`. Removed internal contradictions; marked each item with confirmation status. |
