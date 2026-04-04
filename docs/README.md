# Documentation index

Use this folder as the **entry point** for project and portal rules. File names are stable—prefer linking to these paths from code comments and PRs.

## Current documents (use these)

| File | Purpose |
|------|---------|
| [`PROJECT_CONSTRAINTS.md`](PROJECT_CONSTRAINTS.md) | **Rule book:** portal behaviour, mandatory fields, FSM conventions, known gaps. Validate plans and code against this file. |
| [`portal_field_mapping.md`](portal_field_mapping.md) | **Portal reference:** DOM field names, mandatory flags, address rules—cross-check with live portal when in doubt. |
| [`ISSUES_AND_RESOLUTIONS.md`](ISSUES_AND_RESOLUTIONS.md) | **Tracker:** audit findings, discussion outcomes, and suggested resolution approaches (companion to implementation work). |
| [`audit.md`](audit.md) | **Audit report:** detailed step-by-step logic issues found in the codebase (historical analysis). |

## Archived (do not follow as current truth)

| Location | Purpose |
|----------|---------|
| [`archive/`](archive/) | Obsolete or misleading docs retained only for history. See [`archive/README.md`](archive/README.md). |

## Suggested reading order

1. `PROJECT_CONSTRAINTS.md` — what the system must respect.  
2. `portal_field_mapping.md` — when checking portal field names or mandatory rules.  
3. `ISSUES_AND_RESOLUTIONS.md` — when fixing known bugs or reconciling rules with code.  
4. `audit.md` — when you need the original deep-dive on a specific issue.
