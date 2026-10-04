# Terra Audit: deployed UI/UX audit

Audit performed 4–5 October 2026, Asia/Dhaka, against https://terra-audit.vercel.app. Browser observations were checked against the current repository where necessary. This report records findings; it does not implement changes.

## Decision

Keep the current visual direction and shared components. The main weakness is the journey between registration, evidence, calculation, explanation, and review. Fix those connections and the meaning of displayed results before doing another visual redesign.

The strongest priorities are input provenance, honest credit/status presentation, working evidence-review links, provider-aware AI configuration, and completing the evidence/team workflows already supported by the backend.

## Scope and evidence

The browser pass covered Projects; project Monitoring, Fields, Methodology and AI workspace; Fields and its filters; new-field boundary input; Crop Seasons; Enrollment; Signal Analytics; legacy Carbon Asset Ledger; Calculations and a read-only readiness check; field Edit; Portfolio; Reviews; Product setup; Team and its invite dialog; Worker & queue. Dropdowns, dialogs, the calendar, sidebar collapse, and appearance selection were exercised.

Desktop inspection used the browser's normal viewport, approximately 1536×655. Selected responsive checks used 390×844 and 768×1024. These were viewport checks in desktop Chrome, not tests on physical phones or tablets. Light and System appearance were checked; System resolved to dark on this computer. System was restored and the temporary viewport was reset.

The account contained five rice-pathway fields, one project, one wheat crop season, legacy credit history, and no field observations or attachments. These values describe this account, not every deployment. User-entered names, spelling and large areas were not classified as software defects.

No field/project/evidence was created, deleted or saved. No calculation was previewed or committed. No AI request, satellite run, training job, invitation, indexing job, email or deployment was started. Form values used for inspection were discarded. The only submitted domain request was the existing read-only readiness check.

**Limits:** No ALM field, saved snapshot calculation, or assigned submission was available for the corresponding detailed workflows. The signed-in session redirected `/login` to Fields; it was not logged out. Public authentication forms, ALM-only screens and non-admin behavior were therefore not verified live. Some missing frontend workflows below are supported by code inspection and are explicitly labeled. This is not a security audit, methodology verification, performance benchmark, or proof that every action succeeds.

Priorities: **P1** materially affects trust or completion of a core journey; **P2** causes confusion, accessibility barriers or avoidable friction; **P3** is polish. Nothing in this pass establishes a P0 defect or proves their absence.

## P1: address first

### 01. New calculation inputs look verified but start as generic defaults

**Browser confirmed; source confirmed.** Select the existing season on a rice field, enter the monitoring dates, and inspect Engine inputs. AWD events starts at `0`, season length at `120`, N input at `100`, and amendment rates at `5`. The AWD label says “verified.” Amendment types are raw free-text values such as `straw_shortly_before`.

The same field's legacy ledger explicitly carries over a saved analytics result with **2 events and 84 days**. The newer form gives no provenance explanation for its different defaults. This is a data-entry/trust problem; this audit did not show that a blocked calculation can bypass issuance gates.

**Fix:** start evidence-dependent inputs blank, or prefill only from a compatible saved run with its season, period and source shown. Require explicit manual confirmation when overriding. Use the existing amendment option lists. Keep readiness and engine validation authoritative, and preserve legitimate measured zero values.

Location: `frontend/app/(app)/fields/[fieldId]/calculations/page.tsx`, especially the rice Engine inputs. [Calculation screenshot](ui-audit/2026-10-05/calculation-defaults.jpg), [ledger comparison](ui-audit/2026-10-05/legacy-ledger.jpg).

### 02. Portfolio and legacy ledger overstate the meaning of calculated totals

**Browser confirmed; source confirmed.** Portfolio presents “Rice AWD Credits” in success green and “Aggregated carbon-credit position.” The ledger uses “Final issuance,” “Verification History,” and “Calculate & Save Carbon Credits.” The newer Calculations page identifies those same old records as “legacy · no snapshot,” while the readiness checklist has missing, review and unsupported requirements.

This presentation lets a user confuse a calculated legacy quantity with reviewed/issued credits. It does not establish that the underlying number is mathematically wrong or that registry issuance occurred.

**Fix:** distinguish calculated estimates, legacy results, internal review status and any externally issued quantities. Carry provenance/status into Portfolio rather than summing all non-null results under an unqualified credits label. Show an explicit legacy limitation on the ledger and exports. Do not infer certification from a numeric result or an internal approval.

Locations: `frontend/app/(app)/portfolio/page.tsx`, `frontend/app/(app)/fields/[fieldId]/ledger/page.tsx`, portfolio API/data contract. [Portfolio screenshot](ui-audit/2026-10-05/portfolio-dark.jpg).

### 03. AI's applicability review link leads to a page without the required review task

**Destination confirmed in browser; action mapping confirmed in source.** `common.methodology_applicability` maps to `/projects/{project_id}/methodology`. That page offers bundle selection and eligible-area summaries, not the field/period/requirement determination form. “Record an evidence review” is on Calculations and requires project, seasons, dates and a readiness/preview result.

**Fix:** route the server-owned action to the actual review form with enough validated context to select the field, project, period, seasons and requirement. Add a stable anchor and highlight the requested requirement. A viewer should see whom to ask when they cannot record the review. Keep the backend permission checks intact.

Locations: `src/ai/packets.py` (`REQUIREMENT_FIX_MAP`), project Methodology, field Calculations. A new AI generation was not run to test this link; its configured destination and missing destination task were inspected.

### 04. AI workspace/setup still describe OpenAI and can misreport worker-only configuration

**Browser confirmed; source confirmed.** AI workspace says text/project records are sent to OpenAI and asks for `OPENAI_API_KEY`/`OPENAI_MODEL`. Product setup repeats that instruction. This is inconsistent with the project's Groq explanation configuration and previously supplied successful Groq output.

Both status endpoints use `configured()` with its generation default, while Groq enqueue capability can legitimately require only the model on the API and the key on the worker. Consequently, an API without the worker's Groq key can show the assistant disabled even when queued explanations can run. The status display is confirmed; this exact deployment's environment secrets were not inspected.

**Fix:** provide separate enqueue, worker-generation and visual-OCR capability states. Render the actual provider and the correct configuration guidance. Keep OpenAI-specific wording for the OCR feature that actually requires it. Clearly identify the destination of project data before a user requests a real provider operation.

Locations: `backend/routers/ai_workspace.py`, `backend/routers/product_ops.py`, `src/ai/providers.py`, project AI page. [AI workspace](ui-audit/2026-10-05/ai-workspace.jpg).

### 05. The deployed methodology library is incomplete

**Browser confirmed deployment gap, not a proven ingestion-code defect.** Product setup lists VM0051 as indexed with 143 chunks/90 pages. VM0042, its correction document, VMD0054, VT0014 and its corrections, and the local IPCC documents show zero chunks/not indexed. External references are correctly shown separately.

**Fix:** complete ingestion using the existing job flow and verify it on the shared database/worker. Show coverage for the selected project's bundle on explanation screens. When a relevant document or correction is unindexed, explicitly disclose the missing methodology context; do not let a record-only explanation appear to have methodology-page support. Do not replace missing source material with invented text.

This audit did not start ingestion or assert that every listed source is required for every action. [Setup evidence](ui-audit/2026-10-05/product-setup.jpg).

### 06. Document proposals require attachments, but a general attachment-upload journey is missing

**Browser journey gap; frontend/backend inspection supports it.** AI workspace tells the user to select an already uploaded field/season document. The inspected field/season/project pages have no general evidence-upload action. The backend has authorized `/attachments` upload/list/download endpoints; frontend search found the AI attachment picker, but no corresponding general upload workflow. A GeoJSON boundary upload is a different operation.

**Fix:** add a field/season evidence-files panel using the existing endpoints: upload, identify linked record, list/download, provenance and actionable errors. Connect Document proposals directly to it. Respect retention rules and existing storage configuration. This account's setup reports local storage requiring a shared directory; cross-host storage access was not verified.

Locations: `backend/routers/attachments.py`, project AI page, field evidence UI. ALM-only attachment-reference forms were not verified live.

### 07. Project role management is not available at the normal project setup point

**Browser journey gap; source confirmed.** Team invites users to the organization and says to add them to projects. Product setup asks for project roles. Project navigation has no Members/Access section. The frontend member-add form found in submission detail only adds a contributor; it does not provide normal lead/contributor/viewer management before submissions exist. The backend already exposes project membership endpoints.

**Fix:** add a project Members section for authorized administrators/leads, with the existing role choices and audit reasons. Link to it from Team/setup. Keep organization invitation and project access distinct; do not automatically grant access on invitation.

Locations: project layout/tabs, `frontend/hooks/use-projects.ts`, submission detail member form, `backend/routers/projects.py`. No access permissions were changed during inspection.

## P2: workflow, usability and accessibility

| ID | Finding and evidence | Recommended change |
|---|---|---|
| 08 | **Project context is lost in Reviews.** Clicking the project's Reviews link produces `/reviews?project=...`, but the selector still says “Select a project…” and no submissions load until the user selects it again. `ReviewsPage` initializes an empty state and does not consume the query. | Initialize from a validated accessible project query; keep URL and selector synchronized. [Screenshot](ui-audit/2026-10-05/reviews-context.jpg). |
| 09 | **Stale workers are labeled alive.** Worker & queue showed “alive” next to heartbeats many hours old. The component checks only `stopped_at`, not heartbeat freshness. Multiple identical hostnames make the entries harder to distinguish. | Compute freshness server-side; show active/stale/stopped plus heartbeat age, worker identity and supported job types when recorded. Do not claim a worker is alive from absence of a stop record. [Screenshot](ui-audit/2026-10-05/worker-status.jpg). |
| 10 | **Saved crop seasons have no correction/version UI.** The inspected page offers Add and Select; no correct/history action. Backend `/crop-seasons/{id}/corrections` and `/versions` exist, but no frontend consumer was found. | Expose “Correct season” with a mandatory reason and version history, preserving the season ID and immutable calculation snapshots. Avoid creating duplicate seasons as an accidental workaround. |
| 11 | **Project field rows do not connect to field workspaces.** Assigned fields show raw IDs; Monitoring field/season cells are plain text. Methodology summaries also show raw IDs. | Show name plus ID and links to the relevant field, selected season and eligibility/review work. Make project context available on arrival. |
| 12 | **Signal Analytics' Season selector is actually a fixed set of date presets.** The field has a Winter 26–27 Sep–Oct season, but the selector offers Boro/Aman/Pre-Kharif presets rather than that saved season. | Separate “Crop season” from “Date preset”; populate saved seasons and show the run's actual date range/source. Retain custom ranges as a clearly separate choice. |
| 13 | **Enrollment does not turn a pathway mismatch into a clear next step.** Wheat is shown as VM0051-eligible signal `false`, while Missing evidence says “No basic evidence gaps flagged.” The full checklist later requires applicability review. | Show a prominent fit/review warning, explain the basic-check limitation beside the status, and link to the full readiness/review flow. Offer a history-preserving correction/support path when the registered methodology is wrong; do not auto-switch based on crop taxonomy. |
| 14 | **Several controls lack meaningful accessible names or visible labels.** Confirmed examples: project status filters both called “Choose an option”; unnamed monitoring-selection checkboxes; enrollment inputs; rotation dates both called “Date”; field-edit text inputs. `FieldLabel` renders a sibling label without `htmlFor` support, so ordinary sibling text inputs remain unassociated. | Add explicit `id`/`htmlFor` or wrapping labels; add clear names for filters, row selection, sequence crop/start/end and review controls. Wire helper/error text with `aria-describedby` and invalid states. Preserve hidden native select elements' existing exclusion from assistive technology. [Rotation screenshot](ui-audit/2026-10-05/rotation-labels.jpg). |
| 15 | **New project and invite dialogs lack visible Cancel/Close actions.** Escape works and focus returns to the opener; keyboard containment was present. Touch users should not need to discover backdrop dismissal. | Add a reusable labeled close action and form Cancel button while retaining Escape/focus restoration. [Project dialog](ui-audit/2026-10-05/project-dialog.jpg). |
| 16 | **Dates and number formatting are inconsistent.** Inputs use DD-MM-YYYY; season labels use YYYY-MM-DD; calculation history uses US-style dates and sometimes 15-digit decimal quantities; Team, Portfolio and ledger expose raw ISO timestamps. Worker timestamps alone clearly state browser-local timezone. | Centralize display formatting: DD-MM-YYYY, local time with timezone where relevant, consistent units/precision. Keep ISO/unrounded values in storage and exports. Do not silently change calculations. |
| 17 | **Narrow layouts hide context and crowd content.** At 390px, the active Calculations tab was outside the visible tab strip (its left edge was around 650px); no automatic scroll revealed it. At 768px, the 256px desktop sidebar left only 464px for main content and crowded Monitoring table headings and project tabs. Portfolio tables were contained in horizontal scroll rather than causing body overflow. | Scroll the active tab into view, add a scroll cue, use a later desktop-sidebar breakpoint or compact tablet sidebar, and give dense tables an appropriate minimum width/scroll wrapper or mobile row cards. [Tablet screenshot](ui-audit/2026-10-05/tablet-monitoring.jpg), [mobile screenshot](ui-audit/2026-10-05/mobile-calculations.jpg). |
| 18 | **Train and evaluate is enabled with zero eligible seasons/crops.** The requirement text is clear, but the button invites an operation known to fail. The crop-season benchmark correctly disables its equivalent action. The training endpoint raises `ValueError` for insufficient data; that failure response was not exercised. | Disable using the known eligibility state, show concrete remaining requirements, and return a controlled validation response on the server. Backend checks must remain even when the UI disables the button. |
| 19 | **Failed-job notifications have no recovery path.** Reviews shows failed `ai_explain` notifications with only Mark read. Worker & queue provides aggregate counts and workers, not a navigable failed-job list. Historical errors are not proof that the current worker is failing. | Link to an authorized job detail/source field, show the failure reason and safe retry/request-again guidance. Keep opaque job names in technical details, not the only user-facing explanation. |
| 20 | **Membership copy promises an effective-date control that is absent.** Project Fields says “effective date below”; the form sends only `field_id`. Crop-season guidance also names a nonexistent “Quantification Units tab,” whose actual location is Enrollment. | Correct the instructions or add the intended effective-date input with existing backend validation. Replace stale tab names with actual links. The membership-end form also needs a Cancel action and handled mutation errors (source finding; failure not submitted). |
| 21 | **Collapsing the desktop sidebar removes appearance and logout.** Their controls disappeared from both the screen and accessibility tree, confirmed by the component's `hidden` branch. | Keep a compact account menu/icon with appearance and logout actions available while collapsed. Restore the expanded view afterward. |
| 22 | **Calendar Escape does not dismiss when focus is on the opener.** After opening, focus was on “Open calendar for Start date.” Escape left the dialog open. Escape from the date text editor did close it. The opener lacks the Escape handler present on editor/popup. | Handle Escape from the whole date-control/popup boundary and verify focus lands inside the visible calendar when opened. Keep the requested removal of Today/Clear/Close footer buttons. This is a specific keyboard path, not a claim that all calendar keyboard controls fail. |
| 23 | **Loading can briefly be presented as missing records.** A new visit to Calculations first displayed “No crop seasons recorded yet” before the existing season appeared. | Separate loading, empty, error and ready states. Do not tell users to add duplicate records while the query is still pending. |

## P3: presentation cleanup

### 24. Technical copy and confidence language need a shared editorial pass

“Compliance Audit Trail Ledger” on Signal Analytics overstates what threshold-derived signal observations establish. Several ordinary workflows discuss “this codebase,” “API,” “current bundle marked current,” or “flow keeps working unchanged.” These are useful implementation details but poor primary guidance for a farmer, contributor or reviewer.

Use plain task-focused wording: signal evidence, recorded observations, calculated estimates, review required, and the next action. Keep exact requirement IDs/citations and technical details in expandable secondary content. The Edit page's “Remove and re-register” guidance for changing boundary/methodology also needs a safer explanation of retained history and limitations rather than making deletion sound like routine editing. No deletion behavior was exercised.

Secondary chart labels, metadata and complex requirement text are small/dense in narrow layouts. Increase readability selectively rather than changing every font or adding more green. No formal contrast-ratio or screen-reader conformance certification was performed.

## What worked and should be retained

- The shared dark dropdown visually matches the frosted control system; selection and Escape dismissal worked in the inspected filter.
- The custom calendar fits the tested mobile viewport and uses DD-MM-YYYY. Its removed footer actions remain absent. [Mobile calendar](ui-audit/2026-10-05/mobile-calendar.jpg).
- Light mode renders the inspected portfolio/evidence screens correctly; switching back to System restored dark appearance. [Light portfolio](ui-audit/2026-10-05/portfolio-light.jpg).
- Mobile navigation has a visible close action, contains focus, and closes after navigation. Tables remain in their scroll containers.
- Fields search has a useful no-results message and Clear filters.
- Readiness explicitly distinguishes missing, review and unsupported requirements, and discloses that it is not certification.
- Explain buttons explicitly tell users to select a project when required; the current disabled state is explained.
- The global AI Validation page clearly distinguishes agreement with threshold labels from independent real-world accuracy.
- No error/warning entries were returned by the browser log collector at the end of this pass. That is a narrow observation, not proof of all network/backend success.
- Portfolio bars rendered after chart animation settled. Initial captures with no visible bars were not classified as defects.

## Implementation sequence

1. **Repair navigation and recovery:** Reviews query context; applicability review destination/context; field/season links; correct stale instructions; loading states. These are small changes that unblock users without altering scientific calculations.
2. **Make calculation provenance and status explicit:** replace unsupported defaults, reuse compatible saved evidence, show overrides, standardize amendment choices, and separate legacy estimates from reviewed/issued quantities across ledger, portfolio and exports. Preserve existing engine equations and issuance gates.
3. **Complete existing evidence/access features:** general attachments panel, crop-season corrections/version history, and project Members management. Use existing authorized APIs and retention rules; verify the deployed API/worker file-storage arrangement before enabling document workflows.
4. **Unify AI/operations capability presentation:** provider-aware messages, API enqueue versus worker-generation status, document-index coverage, stale heartbeat handling and actionable job errors. Index missing registered PDFs through the existing process. Do not enable providers or change organization opt-in as a cosmetic fix.
5. **Finish shared component/accessibility/responsive work:** associated labels, modal close/cancel, calendar opener Escape, active-tab visibility, tablet navigation/table layout, compact account access, date/number formatting and clearer product copy.

Each batch should have a small reviewable change set. Verification should cover the actual journey and one regression case rather than rewriting the UI or backend architecture. After implementing, verify role restrictions and ALM/snapshot/submission states with suitable user-owned fixture data; this audit did not create that data.

## Audit deliverables and change status

This Markdown report and 13 selected screenshots in `docs/ui-audit/2026-10-05/` are the only repository additions from the audit. Full application fixes, tests, builds and deployments were not performed in this turn. Remaining captures are in `/tmp/terra-ui-audit-2026-10-04/` for this session. Screenshots contain the signed-in account's UI/data and should be treated as internal audit material.
