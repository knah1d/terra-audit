# Integrated displacement leakage — 29 September 2026

## Implemented flow

Production records → saved leakage assessment → immutable calculation snapshot → VMD0054 v1.1 → VM0042 annual leakage increment → ER/CR allocations → readiness and review.

The Production Records page now saves append-only assessment revisions, loads prior revisions for correction, and shows the calculated result or blocking reason. Assessments are scoped to organization, field, project, methodology bundle, and exact monitoring dates. Each new calculation selects the latest matching revision. Saving parameters does not approve their evidence.

The assessment records annual historical/monitoring labels, dates, commodity units and yield sources, accounting mode, explicit Step 2 choice and justification, regional inputs and evidence, and prior external verification information. Harvest cycles are summed before dividing by the number of years. Incomplete commodities, absent records, mixed units, duplicate commodity/cycle entries, inconsistent dates, and unavailable applicable regional inputs block the calculation. No partial sum may silently become zero leakage.

Calculation snapshots freeze the parameter revision, raw production records, project membership scope, source-document bundle and hashes. The leakage adapter calculates entirely from these frozen inputs. Evidence fingerprints include production records, saved assessment revisions, and relevant project memberships; changed evidence invalidates scoped reviewer determinations. Snapshot construction and commit also check for evidence changes during the workflow.

The engine deducts displacement leakage once. VMD0054 Eq.13 gives cumulative leakage. VM0042 Eq.36 converts the positive change from the prior verification to an annual amount. Corrected VM0042 Eqs.39/42 allocate it to emission reductions and removals before the existing buffer deductions. Cumulative prior values come from explicit, source-referenced external verification evidence and require review; an internal draft calculation is not treated as a verified event.

The Calculations page displays leakage details and provides a scoped review form for project leads/administrators. Numerical completeness requirements cannot be manually overridden. The separate evidence review covers history/rotation completeness, commodity coverage, region and factor suitability, prior verified values, and scope consistency. Other leakage sources require documented non-applicability; applicable sources not quantified by this adapter remain blocking.

The legacy ALM scalar screen no longer governs new calculations. Legacy ALM preview returns an explanatory block, and legacy ALM credit-history writes are rejected. Existing stored history is preserved. New ALM work uses the evidence-linked Calculations workflow. Mandatory unsupported readiness rows now prevent `ready_for_review`; incomplete review can still result in a draft where numerical calculation is possible.

## Source reconciliation

- `methodologies/verra/vmd0054/VMD0054-v1.1.pdf`: §5 requires whole-project accounting; §5.1 defines historical and monitored production; §5.2 is optional mitigation; §5.3 supplies Table 1 and cross-commodity conditions; §§5.4–5.5 give regional carbon-stock change and cumulative leakage.
- `methodologies/verra/vm0042/VM0042v2.2_CC_11JUN2026.pdf`: Eq.36 annual leakage increment and corrected Eqs.39/42 displacement-leakage allocations.
- Crop recurrence in historical sequences is supporting evidence and now requires review rather than automatically satisfying rotation completeness.

## Deliberate supported scope and remaining limitations

1. **Single-field projects only.** VMD0054 requires whole-project accounting. A project with more than one field in its membership history is blocked by this adapter. Combining fields, grouped instance start dates, project-level land-sparing effects, and allocating a project total to field calculations needs a project-level accounting implementation. An arbitrary field-area allocation is not supplied.
2. **Complete anniversary-year periods only.** Historical labels and monitoring labels each represent a full year in chronological order. Multiple harvest cycles share their annual label. Partial-year periods block rather than assuming an annualization convention.
3. **No Step 2 mitigation activity claimed.** The operator must explicitly select and explain this case. Claimed mitigation is unsupported and blocking; LM and ELM are not silently zeroed for such claims.
4. **VMD0054 v1.1 only.** The selected bundle must contain that module. No automatic substitution for an older eligible module version is made.
5. Regional datasets are not automatically sourced. The user supplies values and references for review. Positive net land impact requires the regional land-cover/carbon-pool evidence as well as the factors.
6. Prior cumulative leakage is an externally evidenced input, not an automatically inferred registry balance. Subsequent periods require the immediately preceding verification end date and reference.
7. Cross-commodity mode uses mandatory defaults and requires supporting national-production evidence. Fuelwood cross-commodity scope is blocked; agricultural leakage-only overrides require justification.
8. The pre-existing unresolved multi-year SOC uncertainty block remains. Completing leakage does not establish full VM0042 eligibility or readiness.

## Setup and verification ownership

The existing startup initializer now creates the additive `leakage_assessments` table and refreshes requirement metadata. No new environment variables are required. No initializer or migration was executed during implementation. Restart/migration execution remains with the user.

No tests, compilation, syntax checks, lint, builds, application runs, or deployment were performed. Code and source documents were read, and source diffs were reviewed. Runtime and numerical verification remain outstanding; this document does not certify compliance.

The Calculations history now offers an ALM PDF download through `GET /calculations/{calculation_id}/evidence/pdf`. It uses stored inputs and results, includes internal readiness and status, and labels the output as an estimate. The report includes cumulative/prior/annual leakage, ER/CR allocations, source and assessment references, Step 2 choice, and Step 4 applicability. Historical scalar results remain labeled as historical. Snapshot JSON remains the complete reproducible evidence export. PDF generation/rendering was not executed during this implementation.
