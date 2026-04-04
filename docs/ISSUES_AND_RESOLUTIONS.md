# Issues, Discussion Outcomes, and Resolution Approaches

**Purpose:** This document records issues raised in `docs/audit.md`, follow-up discussion (including constraint contradictions and portal behaviour), and **how each item can be resolved**. It does **not** replace `docs/PROJECT_CONSTRAINTS.md`; when implementation or the official rule book is updated, use this file as a checklist and rationale source.

**Related files:** `docs/audit.md` (detailed findings), `docs/PROJECT_CONSTRAINTS.md` (authoritative constraints — may lag behind discussion captured here).

**Revision note:** Created from audit review + constraint reconciliation discussion (2026). Update this file as new decisions are made.

---

## Part 1 — Agreed policy (from discussion)

These points are **decisions** to reflect in the rule book and implementation when you next edit them.

| Topic | Agreed direction |
|--------|------------------|
| **Portal defaults** | Country and state are **pre-filled** (e.g. India / Delhi) where the portal does that; they are **not** “immutable” in general — they can be changed when the portal allows (e.g. foreign national paths). |
| **Tenanted premises (“current tenant premises”)** | Country = India and state = Delhi are **fixed by the portal**; user cannot change them. Portal scope: Delhi police / PG–tenant verification in Delhi. |
| **`village_town_city`** | **Mandatory in all situations** for **owner** and **tenant** (all tenant address sections you collect), including when the address is outside India. |
| **Foreign country on address tabs that allow it** | When country is set to **non-India**, **state, district, and police station** become **not applicable** on the portal; the portal **automatically** selects the not-applicable behaviour (per stakeholder clarification). **Verify on live portal** during implementation in case any tab behaves differently. |
| **Owner last name / tenant last name** | **Not required** by the portal for owner or tenant. Pre-submit checks and `PROJECT_CONSTRAINTS.md` §1.8 should eventually **match** this (remove or relax last-name requirements). |
| **Telegram UX (Issue A)** | Fix callback-length problems in the most **efficient** way while keeping the conversation flow **simple** for users with mixed technical skill. |

---

## Part 2 — Rule-book reconciliation (foreign address + automation)

`docs/PROJECT_CONSTRAINTS.md` currently mixes **accurate portal notes**, **stale blanket rules**, and **inline draft comments**. The following describes **what to resolve** when merging discussion into the official constraints file.

### 2.1 §1.4 (owner country/state “never written”)

**Tension:** The doc forbids writing owner country/state in automation; the portal **can** be changed for foreign cases; stakeholders clarified pre-fill vs fixed vs changeable.

**Resolution approach:**

- Split into **portal facts** vs **automation strategy**.
- **Automation — Delhi-default path:** It may remain valid to **leave owner country/state untouched** when the session is India/Delhi and you only fill Delhi downstream fields, to avoid breaking dropdown sequencing (existing technical reason).
- **Automation — foreign owner (if in product scope):** If you support owners abroad, §1.4 must **allow** setting owner country (and rely on portal auto N/A for state/district/station). If you **do not** support that yet, state it under **known gaps** (see §5.4) instead of a single global “never write.”

### 2.2 §1.7 and §5.1 (sentinels vs portal auto N/A)

**Tension:** Constraints say special DOM values **must be written via JS** when country is non-India; discussion says the portal **automatically** applies not-applicable fields when country is foreign.

**Resolution approach:**

- Document **observed portal behaviour first** (manual or scripted smoke test): after country → foreign, do state/district/station populate without extra steps?
- If **yes:** Rewrite §1.7 / §5.1 to say automation should **set country (and required text fields)** and **wait for / assert** portal-filled N/A; only document manual sentinel writing if testing proves it is still needed.
- If **no:** Keep sentinel table as fallback for automation.

### 2.3 §2.1 / §2.2 / §2.3 (five mandatory fields, unconditional validation)

**Tension:** Blanket “exactly five fields per section, always unconditional” does not match **tenanted premises** (country/state auto-satisfied, not user-filled) or **foreign** paths (state/district/station are N/A, not real Indian picks).

**Resolution approach:**

- Replace one flat rule with a **per–address-type** table in the rule book:
  - **Owner:** Always require `village_town_city`; require **country** when editable; for **India**, require real state/district/police_station as today; for **non-India**, do **not** force users to pick Indian district/station — align with portal N/A.
  - **Tenanted premises:** Require `village_town_city`, district, police_station (Delhi); country/state **not** user-mandatory (fixed on portal).
  - **Tenant permanent:** Same pattern as owner for India vs foreign; always require `village_town_city`.
- Update §2.3 to **allow country-conditional rules** where they match portal behaviour (contradicts current “must not apply country guards” if left absolute).

### 2.4 §5.4 (owner non-Delhi / foreign)

**Resolution approach:** Align wording with §1.4 split: either **scoped limitation** (“automation only supports Delhi-default owner path”) or **planned foreign-owner path** with explicit steps.

---

## Part 3 — Audit issues and how to resolve each

References: `docs/audit.md` (full step-by-step). Below: **resolution approach** only.

| ID | Short title | Resolution approach |
|----|-------------|---------------------|
| **1** | Tenant ID image never sent to portal | Persist tenant image bytes on the session (or re-download from Telegram by stored file id at submit time). Pass non-empty bytes into `SubmissionInput` / `FormFiller._fill_document_upload()`. Add a constraint line: submission **must** attach tenant proof when the portal requires it. |
| **2** | No validation at intermediate confirm steps | In `confirm_owner`, `confirm_tenant`, `confirm_tenanted_addr` (and any similar), call the same **section-scoped** mandatory checks used at final submit. Block transition with a clear message listing **only that section’s** missing fields. |
| **3** | Overview refresh fails silently | On `edit_message_text` failure: log, then **send a new overview** and update `overview_message_id`. Optionally notify the user briefly. |
| **4** | District name mismatch (e.g. SOUTH EAST vs SOUTH-EAST) | Single source of truth: align `police_stations.json` / `StationLookup` output with `DISTRICT_VALUES` keys, or normalize at save time (alias map). |
| **5** | Owner reuses tenanted FSM states | Add `PICKING_OWNER_DISTRICT` / `PICKING_OWNER_STATION`; route owner edits only through them (matches `PROJECT_CONSTRAINTS.md` §3.1 intent). |
| **6** | Callbacks lack FSM state guards | Register critical callbacks with **state filters**, and/or **session generation tokens** in callback data so stale messages no-op. Prefer state guards for maintainability. |
| **7** | `/start` mid-flow leaves stale buttons | On new session: **strip reply markup** from known prior messages if feasible, or combine with Issue 6. Consider **confirm before wipe** if session has data (see §5.7). |
| **8** | No message handler for `PICKING_PERM_DROPDOWN` | Add handler: either mirror occupation search if applicable, or reply “Please use the buttons below” so typing is not a dead end. |
| **9** | Owner state mandatory in bot but not written on portal | After rule-book split (Part 2): if owner stays **India/Delhi default** on portal for supported flows, **drop** `owner.address.state` from mandatory **or** document why it is collected for display only. Align `owner_missing_mandatory()` and `_fill_owner_tab()` with the same story. |
| **A** | Tenant ID proof picker exceeds Telegram 64-byte `callback_data` | Use **numeric indices** or short codes in callback data; map back to full option strings server-side (same pattern as field selector). Verify with `len(...encode("utf-8"))` per §3.4. |
| **B** | Foreign permanent address deadlock in FSM | Implement country + city flow for tenant permanent; rely on portal N/A (Part 2). Unblock `confirm_perm_addr_and_submit` validation to match India vs foreign rules. |
| **C** | Re-upload after pipeline error accumulates image records | On pipeline failure or explicit “replace”, **remove** prior `ImageRecord` entries for that person (or replace list policy). Document in §3.6 if behaviour changes from append-only. |
| **D** | Post-submission dead end | After enqueue: move FSM to a **terminal or idle** state; on worker success/failure: send outcome + **clear prompt** (“Send /start for a new application”). Optionally clear session per policy. |
| **E** | Pipeline error — no buttons after error | After showing error, re-send **upload instructions + same keyboard** pattern as initial upload step. |
| **Elevated** | §1.4 vs owner `state` mandatory | Same as Issue **9**, explicitly cite §1.4 when updating constraints. |
| **F** | OCR district e.g. “South Delhi” vs portal keys | Add **district normalisation** (aliases / mapping) analogous to `STATES.normalize()`, fed from real OCR logs. |
| **G** | Last names required in filler but optional on portal | Remove `ownerLastName` / `tenantLastName` from `_validate_required_fields_before_submit()` (or make optional). Update §1.8 and any FSM copy if needed. |
| **H** | Station label mismatch (e.g. IITF) | Reconcile `delhi_police_stations.json` with `POLICE_STATION_VALUES` keys; one generated from the other or shared normalisation. |
| **I** | Obsolete FSM planning doc described non-existent code | **Done (docs cleanup):** moved to `docs/archive/obsolete_fsm_dependency_map.md` with an obsolete banner. Use `docs/PROJECT_CONSTRAINTS.md` + `features/data_verification/` for current architecture. |

---

## Part 4 — Constraint contradictions — status

| Contradiction | Status |
|---------------|--------|
| Owner `state` required in bot vs filler “do not write” | **Open** until Part 2 + Issue 9 are applied in code and `PROJECT_CONSTRAINTS.md`. |
| Last name required in pre-submit vs portal optional | **Policy resolved** (optional); **implementation/docs** may still lag — resolve via Issue **G** + §1.8. |
| §3.4 “~61 byte” longest `picker:small:` vs tenant doc-type overflow | **Open** in doc accuracy — fix via Issue **A** + update §3.4. |
| §1.1 inline note (normalisation) | **Open** — resolve wording: free text vs picker-only normalisation. |
| Foreign path: sentinels vs portal auto N/A | **Policy direction** from discussion (auto N/A); **rule book** must be updated after live portal check (Part 2.2). |

---

## Part 5 — What is **not** yet updated in the repo

The following remain **as-is** until someone edits them deliberately:

- **`docs/PROJECT_CONSTRAINTS.md`** — Does not yet incorporate Part 1–2 or remove conflicting §2.3 / §1.7 / §5.1 wording.
- **`docs/audit.md`** — Remains the raw audit narrative; it is not automatically synced with this tracker.
- **Application code** — Unchanged by this document alone.

---

## Part 6 — Suggested order when applying changes

1. **Live portal check** — Foreign country → confirm state/district/station auto-behaviour (Part 2.2).
2. **Update `PROJECT_CONSTRAINTS.md`** — Part 1 + Part 2 + Part 4 (single voice, remove obsolete parentheticals).
3. **Critical submission blockers** — Issues **1**, **G**, **A** (user cannot complete or fix data).
4. **Data alignment** — **4**, **F**, **H**.
5. **FSM safety / UX** — **2**, **3**, **6**, **7**, **8**, **D**, **E**, **B**, **C**.
6. **Structural** — **5**, **9**, **I**.

---

## Revision history

| Date | Change |
|------|--------|
| 2026-04-04 | Initial consolidation from audit review, constraint contradiction thread, and stakeholder clarifications (portal defaults, village_town_city, foreign N/A, last names, tenanted fixed). |
