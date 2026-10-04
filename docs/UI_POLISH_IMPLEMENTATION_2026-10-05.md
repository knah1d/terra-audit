# UI polish follow-up — 5 October 2026

Implemented following the shared styling and workflow batch:

- Standardized remaining displayed history dates across monitoring, methodology decisions, reviews, AI workspace and crop observations. Calendar dates use DD-MM-YYYY; timestamps keep local browser time and timezone. API and stored ISO values are unchanged.
- Applied shared numeric formatting to production quantities, area shares and calculation estimates. Non-finite display values render as unavailable, never as zero.
- Named rotation controls, quantification-unit controls and issue-resolution controls. Rotation entries stack on narrow screens. Geometry upload/paste IDs no longer collide with the registration form.
- Shared validation errors announce themselves; registration input errors are explicitly associated with their controls.
- Notifications resolve existing issue and batch references into recovery links. Batch links select the referenced monitoring batch.
- Newly exhausted worker jobs retain a job reference on their notification; recovery links open the original AI workspace, calculation, signal analysis or crop evidence page. Links do not automatically retry or modify evidence. All lookups retain organization/user scoping, and destination APIs enforce current access.

## Compatibility and rollout

One additive nullable `notifications.job_id` column is created through the existing SQLite/Postgres initialization paths. Restart updated API and worker normally after deployment; no manual database reset is needed. Older job notifications without a stored reference cannot be reliably linked retrospectively. Existing issue/batch notifications can be linked.

No app startup, build, tests, provider requests, methodology ingestion or deployment was performed for this follow-up, per the user's instruction. Verification remains with the user.

## Remaining audit work

- Review the changed deployed UI in both themes and on small screens.
- Address methodology-library ingestion coverage through the existing authorized ingestion flow; inspect correction citations afterward.
- Run the planned AI evaluation cases before claiming production-quality explanations.
