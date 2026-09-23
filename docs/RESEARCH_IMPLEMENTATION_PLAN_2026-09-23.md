# Terra-Audit research and implementation plan

Research date: 23 September 2026. Scope: source review and planning; no application implementation, tests, builds, or deployment in this review.

## Recommendation

Continue toward a multi-crop agricultural measurement, reporting, and verification product. The next work should strengthen methodology applicability, historical evidence, and calculation controls before expanding AI. Supporting a crop in records, recognizing it with AI, and supporting a crediting claim for it are three separate capabilities.

Keep one shared farm/field/crop-cycle data system, with versioned methodology adapters and task-specific AI models. Do not duplicate the application for each crop or assume a recognized crop automatically qualifies for carbon accounting.

This is a targeted review: all 14 local PDFs were inventoried and text-extracted; relevant requirements and code paths were inspected. It is not a complete equation-by-equation certification or an exhaustive review of the literature.

## Existing implementation

The workspace already contains project/farm membership, crop seasons and practices, evidence attachments, calculation snapshots, readiness checks, reviewer workflows, durable jobs, AI model management, a project-evidence assistant, OCR proposals, account access, and operational configuration.

The ALM calculator already implements several emissions components, measured-soil stock changes, uncertainty deductions, buffer handling, and production-decline screening. These should be extended and reconciled, not re-created. Current coverage remains a subset of the named methodologies.

## Local methodology inventory and implications

| Documents present | Implication |
| --- | --- |
| VM0042 v2.2 and 11 June 2026 corrections | Treat the base document and corrections as one controlled bundle. Baseline rotations, eligibility areas, quantification units, and leakage require explicit representation. |
| VM0051 v1.1 and an archived v1.0 | Keep version eligibility tied to project milestones; the folder name `superseded` alone cannot determine whether a project may continue using v1.0. |
| VT0014 v1.0 and 16 October 2025 corrections | Digital soil mapping needs measured soil data, project-area validation, uncertainty handling, and reproducible model records. |
| VCS Program Guide, Standard, Registration and Issuance v5.0 | Add effective-date and correction dependencies; avoid assuming every existing project immediately follows every v5 rule. |
| IPCC 2019 refinement Volume 4 chapters 2, 5, 10, 11 | Maintain parameter provenance and geographic applicability; these are not a substitute for project methodology requirements. |
| FAO GSOC MRV protocol | Useful supporting guidance for sampling and laboratory workflows; do not treat it as an independent authorization to issue credits. |

Missing from this folder: VT0008 additionality, VMD0053 model guidance, VMD0054 leakage, and current VCS effective-date/correction documents. Inventory applicable risk tools and reporting templates as further dependencies.

Official sources checked:

- [VM0042 v2.2](https://verra.org/methodologies/vm0042-improved-agricultural-land-management-v2-2/) remains the published current methodology; its v3 revision is under development. The [June 2026 correction notice](https://verra.org/program-notice/corrections-and-clarifications-to-ialm-methodology-vm0042/) means a version label alone does not identify the complete rules used.
- [VM0051](https://verra.org/methodologies/improved-management-in-rice-production-systems/) v1.1 became active on 14 July 2026. The page describes transition eligibility for v1.0 and its August 2027 inactivation. Model version selection must preserve eligible historical projects.
- [VMD0054 v1.1](https://verra.org/methodologies/vmd0054-estimating-leakage-from-the-displacement-of-agricultural-activities-v1-1/) became active on 13 January 2026. It addresses new commodities and revised ecosystem assumptions. The current engine references v1.0 screening, so this needs a deliberate versioned implementation, not a renamed constant.
- [VMD0053 v2.1](https://verra.org/methodologies/vmd0053-model-calibration-validation-and-uncertainty-guidance-for-the-methodology-for-improved-agricultural-land-management-v2-1/) provides the model calibration, validation, and uncertainty framework relevant to a future biogeochemical modeling pathway.
- [VT0008](https://verra.org/methodologies/vt0008-additionality-assessment/) supplies additionality procedures, with the applicable methodology determining which procedures apply.
- [VCS program details](https://verra.org/programs/verified-carbon-standard/vcs-program-details/) list effective-date guidance and June 2026 program corrections. Store these alongside the methodology bundle.

## Concrete implementation gaps

1. `src/readiness.py` currently treats a matching field-type/pathway mapping as methodology applicability. Replace this with actual conditions and supporting evidence. A present baseline dictionary also does not establish a complete historical baseline.
2. Manual determinations can replace automated statuses, including unsupported requirements. Limit decisions to explicitly reviewable requirements. Scope each decision to the project, methodology bundle, period, evidence version, and authorized reviewer; expire it when its inputs change.
3. `src/issuance.py` allows missing compatibility flags by default. Preserve historical records, but require new claim-ready results to pass a common explicit gate across every calculation entry point. An internal approval must remain distinct from external registry issuance.
4. Historical activity data must represent at least the applicable look-back and full crop rotation. Model sequential crops, intercropping, cover crops, fallow, quantities, units, and commodity-specific yields. Date-span checks alone cannot prove complete records.
5. The ALM engine explicitly excludes some calculations and leakage components. Build a source-by-source applicability matrix; implement applicable gaps or return a specific unsupported outcome. Do not silently interpret missing data as zero or not applicable.
6. Soil inputs need traceable samples, strata, controls, depths, bulk density, laboratory evidence, and consistent measurement methods. Current aggregate stock inputs are not the whole sampling workflow.
7. Reconcile equations and units before extending calculations. In particular, inspect annualization in the ALM SOC uncertainty denominator and variance conversions against the applicable source. This is a review concern, not a runtime-confirmed defect. Distinguish uncertainty deductions from non-permanence buffer contributions in both calculation and UI explanations.
8. Current factor defaults are geographically scoped. Parameter selection needs source/version, climate/region, unit, applicability, and reviewer-visible override provenance.
9. The assistant retrieves project evidence but does not yet expose a controlled methodology corpus with correction precedence and section/page citations.

## Recent research and reusable projects

These findings guide architecture; none establishes accuracy for all crops or for Bangladesh.

| Source and publication status | Finding relevant to this product | Proposed use |
| --- | --- | --- |
| [Foundation Models Meet Agriculture](https://arxiv.org/abs/2608.30392), 31 August 2026 preprint | Performance varies across agricultural tasks and input modalities. | Retain RF/XGBoost baselines; combine imagery with weather, soil, and management data where appropriate. |
| [SwissCrop25](https://arxiv.org/abs/2608.09497), 10 August 2026 preprint, accepted ECCV TerraBytes II workshop | Multi-year crop classification explores detailed taxonomy and temperature-informed phenology; model rankings depend on setting. | Add crop-cycle windows, thermal-time features, unknown classes, and separate early-season outputs. |
| [Benchmarking Geospatial Foundation Models for Agriculture Applications](https://arxiv.org/abs/2606.29664), 29 June 2026 preprint submitted to ACM SIGSPATIAL | Regional generalization and class imbalance remain important limitations. | Store geographic/crop scope and abstention policies with each model; provide regional performance records. |
| [WorldCereal deployment lessons](https://proceedings.mlr.press/v292/butsko25a.html), 2025 ICML TerraBytes workshop proceedings | Operational crop mapping requires task adaptation and domain-specific evaluation. | Introduce a controlled pretrained-model adapter after the input contract is stable. |

Implementation references:

- [WorldCereal Prometheo](https://github.com/WorldCereal/prometheo): candidate infrastructure for Presto-based representations. Capture band ordering, units, masks, timestamps, input modalities, software versions, and checkpoint hashes. Existing six-band field summaries are not automatically compatible pretrained inputs.
- [Microsoft rice irrigation mapping](https://github.com/microsoft/rice-irrigation-mapping-s1s2): useful reference for a specialized rice irrigation model using Sentinel-1/2. It does not supply a universal crop or crediting engine.
- [Fields of the World baselines](https://github.com/fieldsoftheworld/ftw-baselines): candidate for later field-boundary suggestions and geometry checks, after core monitoring workflows work.

Also located a July 2026 [digital soil mapping MRV article](https://www.nature.com/articles/s44264-026-00125-0). Full-text access failed during this review; it is a follow-up reading item, not the basis for an implementation claim here.

## Implementation order

### Phase 1 — Methodology registry and reliable readiness

Implement a source registry with document hashes, versions, publication/effective dates, corrections, dependencies, and project applicability. Add a requirements matrix: requirement → source section → required evidence → calculation support → reviewer authority → blocking behavior.

Replace routing-only eligibility, restrict manual overrides, scope decisions to evidence versions, and unify new-result readiness gates. Separate estimate, internally reviewed, externally verified, and registry-issued states. Preserve immutable historical results.

Deliverable: every readiness outcome identifies the applicable rule, its evidence, and any unsupported calculation. Primary touchpoints: `src/readiness.py`, `src/calculations.py`, `src/issuance.py`, calculation APIs, project settings, and calculation screens.

### Phase 2 — Complete multi-crop evidence records

Extend the existing crop-season model with crop taxonomy, crop mixtures, rotation history, fallow periods, field subdivisions/quantification units, and grouped-project eligibility areas. Support historical and project-period practices, irrigation, fertilizer, residue, grazing, and commodity-specific yields with explicit units and source attachments.

Add guided enrollment that explains eligible pathways and missing evidence. Rice methane reductions use the appropriate VM0051 scope. Rice SOC claims require a separate applicability and implementation assessment; do not automatically route them into the current non-wetland ALM subset.

Deliverable: a field can contain different crops over time or mixtures within a season while retaining the correct history and accounting boundaries.

### Phase 3 — Calculation coverage and soil evidence

Reconcile current implemented equations and correction handling, then address applicable missing sources, including liming and leakage. Implement version-aware VMD0054 requirements, with commodity-aware displacement inputs; retain explicit blocks for unsupported cases.

Add sampling plans, geolocated samples, depth intervals, bulk density, lab results, strata/control links, chain of custody, measurement-method changes, and uncertainty provenance. Handle permanence risk separately. Show supported quantification approaches explicitly; do not imply QA1 support before its model workflow exists.

Deliverable: calculations can be traced from activity or sample through factor/equation to result, with the exact scope and missing requirements visible.

### Phase 4 — AI throughout evidence and monitoring

First, ingest the controlled methodology bundles into retrieval alongside project evidence. Preserve pages/sections, effective scope, correction precedence, and document hashes. AI may explain requirements, propose extracted records, flag inconsistent evidence, and draft report text. Users approve proposals; deterministic rules own readiness and calculations.

Next, add a common satellite/weather feature contract and task-specific model adapters: crop classification, phenology, rice irrigation, and anomaly detection. Register training scope, input contract, calibration evidence, checkpoint digest, and abstention conditions. Keep present baselines available and introduce Presto only as an optional adapter.

Deliverable: AI suggestions carry source evidence, model identity, scope limitations, and review status. Low-confidence or out-of-scope predictions remain unknown rather than becoming compliance facts.

### Phase 5 — Complete the reviewer workflow

Generate a reproducible review package containing methodology bundles, baseline/monitoring records, evidence indexes, calculation snapshots, uncertainty/leakage details, findings and responses, and report drafts. Add project-level missing-evidence tasks, monitoring deadlines, and consolidated review status. Record external verification and issuance references separately from internal actions.

Deliverable: an analyst can enroll fields, collect evidence, calculate, resolve findings, and hand over a coherent review package without reconstructing it manually.

### Later expansion — Digital soil mapping and biogeochemical models

Implement these as distinct approaches only after measured-soil workflows are available. [VT0014](https://verra.org/methodologies/vt0014-estimating-organic-carbon-stocks-using-digital-soil-mapping-v1-0/) requires a specific DSM workflow; the local document includes project-area validation, stock-level validation, independent data handling, prediction intervals, and reproducibility requirements. A crop embedding alone does not establish SOC stock change.

Record/import scientific validation evidence and independent expert review where required. The user remains responsible for executing testing and deployment; building these evidence-management features does not mean running those activities now.

## Product boundary

The practical next release should support broad crop recordkeeping with explicit, narrower methodology and AI coverage. Publish a capability matrix by land use, practice, region, quantification approach, and model task. An unsupported crop/activity combination can still be monitored without presenting it as eligible for a quantified claim.

Defer universal crop accuracy promises, automatic soil credits from imagery, autonomous compliance approval, and registry automation until their specific prerequisites are implemented. The immediate next implementation is Phase 1, followed by the multi-crop evidence model in Phase 2.
