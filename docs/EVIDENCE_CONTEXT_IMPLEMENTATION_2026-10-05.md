# Evidence context and corrected-season implementation

## Implemented

- Added an organization-scoped current-season projection with stable logical season IDs and an explicit immutable `version_record_id`. The existing raw list remains the default; clients opt in with `current_only=true`.
- Calculations, crop-season workspaces, evidence attachments and signal analytics now share the current-season query. Corrections no longer become extra season choices, and existing attachments and monitoring jobs retain the stable season target.
- Project dashboards and live enrollment/historical coverage use latest corrected season payloads. Superseded dates and crop declarations no longer contribute to current coverage. Raw history, calculation snapshots and field-wide evidence fingerprints are preserved.
- Readiness and previews are displayed only for their captured project, dates, selected season IDs and season versions. Editing engine inputs invalidates a preview, including a response that completes after an edit. Context controls are disabled during calculation/review requests.
- Field or query-context navigation remounts calculation, season and attachment workspaces to prevent state leaking into another task.
- Invalid date ranges, missing seasons and inaccessible projects block calculation requests with recovery guidance. Unavailable season selections can be removed explicitly.
- The evidence review form follows project-lead/admin permissions, preselects only a reviewable requested requirement, highlights the requested checklist row, and refreshes readiness after a saved determination.
- Reviews links retain project context; calculation-history failures appear as errors rather than empty history.

## Verification boundary

Reviewed changed source and references only. No tests, build, type checks, application startup, live indexing, provider requests or deployment were run, as requested. Runtime behavior remains for user verification. Backend authorization is unchanged and remains authoritative. This batch does not claim completion of every original browser-audit finding or provider evaluation.
