# Project Documentation — Navigation Hub

Start here. Every other doc in this folder is linked below with a one-line description of when to use it.

---

## Living Documents (keep these up to date)

| File | What it answers |
|------|-----------------|
| [`OVERVIEW.md`](OVERVIEW.md) | What is this project, who uses it, and how does the flow work? |
| [`REQUIREMENTS.md`](REQUIREMENTS.md) | What must the system do, and what does success look like? |
| [`CONSTRAINTS.md`](CONSTRAINTS.md) | What rules must every plan and code change respect? |
| [`ISSUES.md`](ISSUES.md) | What is currently broken or incomplete, and how urgent is it? |
| [`portal_field_mapping.md`](portal_field_mapping.md) | What are the exact field names, dropdown values, and portal rules? |

## Suggested reading order

1. **`OVERVIEW.md`** — understand the project before anything else.
2. **`REQUIREMENTS.md`** — understand what done looks like.
3. **`CONSTRAINTS.md`** — understand what you must not break.
4. **`ISSUES.md`** — understand what is currently known to be broken.
5. **`portal_field_mapping.md`** — look up specific portal fields when writing or reviewing submission code.

## Archived Documents (do not use as current truth)

| File | Why archived |
|------|--------------|
| [`archive/audit.md`](archive/audit.md) | Original audit narrative. Findings have been summarised in `ISSUES.md`. |
| [`archive/ISSUES_AND_RESOLUTIONS.md`](archive/ISSUES_AND_RESOLUTIONS.md) | Earlier issue tracker. Superseded by `ISSUES.md`. |
| [`archive/obsolete_fsm_dependency_map.md`](archive/obsolete_fsm_dependency_map.md) | Describes an FSM that does not exist in the current code. |

---

## How to update these docs

- **Found a new constraint?** Add it to `CONSTRAINTS.md` under the right section. Note the date.
- **Found a new bug or gap?** Add it to `ISSUES.md`. Set priority and status.
- **Something got fixed?** Update the status in `ISSUES.md`. Do not delete the row.
- **Portal behaviour confirmed by live test?** Update `portal_field_mapping.md` and note it as confirmed.
- **Requirements changed?** Update `REQUIREMENTS.md` and note what changed and why.
