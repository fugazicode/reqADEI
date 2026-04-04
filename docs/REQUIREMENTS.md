# Requirements and Expected Outcomes

**Last updated:** 2026-04-04

---

## How to read this document

- **Must** = non-negotiable. The system does not work correctly without this.
- **Should** = strongly preferred. Absence causes a poor experience.
- **May** = optional enhancement. Nice to have.
- **Must NOT** = a rule that must never be violated.

Each requirement has a status:
- ✅ **Done** — implemented and working
- ⚠️ **Partial** — partially implemented or has a known flaw
- ❌ **Missing** — not yet implemented
- 🔒 **Blocked** — depends on something external (e.g. portal behaviour)

---

## Section 1 — Image Upload and Data Extraction

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 1.1 | The bot **must** accept one or more Aadhaar card photos from the owner | ✅ Done | |
| 1.2 | The bot **must** accept one or more Aadhaar card photos for the tenant | ✅ Done | |
| 1.3 | The bot **must** extract name, address, Aadhaar number, date of birth, and relation info from photos | ✅ Done | Uses Groq vision |
| 1.4 | The bot **must** validate that the extracted Aadhaar number passes the Verhoeff checksum | ✅ Done | |
| 1.5 | The bot **must** detect and reject duplicate Aadhaar cards (same card used for both owner and tenant) | ✅ Done | |
| 1.6 | When a pipeline error occurs, the bot **must** show the error and prompt the user to re-upload | ⚠️ Partial | Error shown, but no re-upload button is displayed — see Issue #E |
| 1.7 | Re-uploading after a failed extraction **must** replace the previous images, not accumulate them | ❌ Missing | See Issue #C |

---

## Section 2 — Review and Edit Flow

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 2.1 | After each upload, the bot **must** show all extracted fields on a review screen | ✅ Done | |
| 2.2 | The user **must** be able to edit any field shown on a review screen | ✅ Done | |
| 2.3 | Fields that accept only specific values (e.g. state, district, occupation) **must** use a picker, not free text | ✅ Done | |
| 2.4 | Fields that accept any text (e.g. house number, street name) **must** accept free text input | ✅ Done | |
| 2.5 | Mandatory fields that are still empty **must** be visually flagged (⚠️) on the review screen | ✅ Done | |
| 2.6 | Before advancing past each review section, the bot **must** check that all mandatory fields for that section are filled | ❌ Missing | See Issue #2 — currently only checked at final submit |
| 2.7 | The review screen **must** stay visible and update in place when a field is edited | ⚠️ Partial | Fails silently if the message was deleted — see Issue #3 |
| 2.8 | The picker for tenant ID proof type **must** work within Telegram's 64-byte button limit | ❌ Missing | See Issue #A — currently all buttons exceed the limit |

---

## Section 3 — Address Collection

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 3.1 | The bot **must** collect the address of the rented property (tenanted address) as free text | ✅ Done | |
| 3.2 | The tenanted address **must** always be in Delhi — state and country are fixed automatically | ✅ Done | |
| 3.3 | The tenanted address **must** include a district and police station selected from Delhi-only pickers | ✅ Done | |
| 3.4 | The tenant's permanent address **must** include village/town/city, country, state, district, and police station | ✅ Done (India path only) | |
| 3.5 | The village/town/city field **must** always be filled, even for foreign addresses | ✅ Done | |
| 3.6 | For non-India permanent addresses, state/district/police station **must** be set to "Not Applicable" on the portal | ❌ Missing | See Issue #B — causes deadlock for foreign tenants |

---

## Section 4 — Portal Submission

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 4.1 | The bot **must** log in to the Delhi Police portal and fill all form fields automatically | ✅ Done | |
| 4.2 | The bot **must** upload the tenant's Aadhaar card scan to the portal as the identity document | ❌ Missing | See Issue #1 — the most critical bug; image bytes are always empty |
| 4.3 | The bot **must** submit the form and capture the Service Request Number | ✅ Done | |
| 4.4 | The bot **must** retrieve the PDF confirmation and send it to the user on Telegram | ✅ Done | |
| 4.5 | The bot **must NOT** include last name in submission validation, as the portal does not require it | ❌ Missing | See Issue #G — single-name Aadhaar cards always fail |
| 4.6 | After submission (success or failure), the bot **must** tell the user what happened and what to do next | ❌ Missing | See Issue #D — bot goes silent after submission |

---

## Section 5 — Session and Safety

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 5.1 | Sending `/start` mid-flow **should** warn the user before wiping their in-progress session | ❌ Missing | See Issue #7 |
| 5.2 | Old buttons from a previous session **must NOT** be able to affect a new session | ❌ Missing | See Issue #6 |
| 5.3 | The bot **must NOT** store Aadhaar numbers beyond the active session | ✅ Done | Sessions expire after 24 hours |
| 5.4 | The bot **must** require explicit consent before collecting any identity documents | ✅ Done | |

---

## What does success look like?

A successful end-to-end run means:
1. Owner uploads both Aadhaar cards → data is read correctly
2. Owner reviews and corrects any mistakes → all mandatory fields are filled
3. Bot submits the form to the Delhi Police portal → no validation errors
4. The tenant's Aadhaar scan is attached to the portal submission
5. Bot sends the PDF confirmation to the owner on Telegram
6. Owner receives a valid Service Request Number

**Current state:** Steps 1, 2, 3 work for the common India/Delhi path. Step 4 never works (Issue #1). Steps 5 and 6 work when step 3 succeeds.

---

## Out of scope (current version)

- Owners or tenants with addresses outside India
- Registering more than one tenant per session
- Family members residing with the tenant
- Tenant previous address (only permanent address is submitted)
- Admin dashboard or reporting

---

## Revision history

| Date | Change |
|------|--------|
| 2026-04-04 | Initial creation from codebase audit and constraint review. |
