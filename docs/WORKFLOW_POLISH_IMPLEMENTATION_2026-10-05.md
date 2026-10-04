# Calculation, AI, queue and navigation improvements

## 1. Saved calculation inputs

- New read-only, field-authorized `/fields/{field_id}/signal-runs/evidence` endpoint offers up to 20 field runs from the latest 200 completed signal jobs in the organization.
- Rice calculation forms explicitly offer matching field/area/date runs. Choosing one copies AWD events and season length; other scientific inputs remain manual. Editing inputs clears preview validity and requires renewed evidence confirmation.
- Optional `signal_run_id` is revalidated server-side during preview and commit. Wrong tenant, field, pathway, period or area is rejected.
- Snapshots preserve source job ID, completion time, detector, original values and manually overridden input names. Reviewers see those details. Older snapshots disclose their lack of a link.
- No new database columns or engine equations. Signal jobs do not freeze boundary/season versions, so the UI and snapshot disclose that limitation. Cache-only runs without a durable completed job are not offered as linked evidence.

## 2. Result wording

- Removed remaining user-facing “Final issuance” labels in review and rice derivation views.
- Calculation history explicitly labels quantities as estimates; portfolio tooltips label legacy estimates. Existing internal approval/registry issuance distinctions remain.
- Review monitoring dates use DD-MM-YYYY and quantities use shared numeric precision.

## 3. AI coverage

- Every draft explains whether its citations include documents or only project records, with a link to bundle/index/correction coverage.
- Incomplete coverage and unconfirmed corrections automatically expand document details. Existing server-owned missing/stale-source and correction limitations remain in place.
- Explanation failures give configuration/evidence recovery guidance. Modal scrolling and accessible naming are improved.
- No indexing, correction confirmation or provider calls were performed.

## 4. Worker recovery

- Queue UI adds manual refresh, no-recent-heartbeat warnings, job-type counts and specific pending/running/cancellation guidance.
- Recent job recovery metadata preserves project, requirement, seasons and dates. Links route indexing to setup and crop monitoring to crop seasons.
- Heartbeats are explicitly distinguished from job progress and job-type eligibility. Failed jobs are not blindly retried or deleted.

## 5. Responsive and accessibility

- Shared horizontal reveal logic keeps active field/project tabs visible without scrolling the page vertically.
- Segmented controls support Arrow/Home/End focus navigation while preserving normal activation.
- Monitoring tables have a labelled keyboard-focusable scroll region, a caption, column scopes and local completion timestamps.
- Portfolio charts retain a minimum readable width and horizontal scrolling on narrow screens. Existing frosted glass styling is preserved.

## Verification boundary

Changed code and references were reviewed manually. No tests, builds, lint, type checks, app startup, deployment, live indexing or provider evaluation were run, per the user’s instruction. This is implementation completion for the five scoped areas, not a claim that every browser-audit issue or production scenario is verified.
