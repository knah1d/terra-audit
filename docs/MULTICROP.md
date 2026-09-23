# Multi-crop monitoring and benchmark pilot

## Available now

In the Next.js app, open a field and select **Crop Seasons**. This works for
both `rice_awd` and `cropland_alm_vm0042` fields. Register any named crop or
crop mixture and a monitoring period (at most two years). Annual rotations
use successive seasons; perennial crops use successive monitoring periods.
Existing field types, practice schedules, SOC measurements and carbon engines
are preserved. Seasons do not automatically select or change methodologies.

1. Add a crop season with inclusive start/end dates.
2. Record dated observations with a source and an evidence reference. Water
   levels are centimetres relative to the soil surface (negative below it);
   residue cover is percent. Photos and documents are referenced, not uploaded
   or interpreted by an AI in this release.
3. A different admin/analyst reviews an observation and records their reason.
   Reviews are append-only; the latest decision governs benchmark eligibility.
4. Collect observations for a completed season. The generic pipeline is
   available for every crop, independently of the rice-only AWD detector.
5. Export the evidence package or run an organization-wide crop benchmark.

## Observation processing

`multicrop-s1-s2-v1` retrieves descending Sentinel-1 IW VV/VH and Sentinel-2
harmonized surface reflectance through the configured Earth Engine account.
Sentinel-1 dual-pol RVI uses linear power. Sentinel-2 masks to SCL classes
4/5/6 (vegetation/bare soil/water), scales reflectance by 0.0001, and computes
NDVI, NDMI and NDTI. These indices do not establish a management practice.
Optical summaries use a 20 m grid; radar summaries use 10 m. Each scene keeps
its identifier, date, valid fraction and radar relative orbit where applicable.
No weather inputs are included in this version.

The screen requires at least five usable dates per sensor, no gap longer
than 30 days (including season edges), and at least 50% valid coverage per
usable scene. These are provisional engineering thresholds, not validated
agronomic thresholds. Cloud masking errors and mixed pixels in small fields
remain limitations. Failed coverage is reported as insufficient evidence.

Every successful collection creates an immutable database record containing
the season, field geometry/metadata, source collections, version, observations,
and quality results. Re-collection appends a new run. The evidence export
includes all runs, observations and reviews with a SHA-256 content digest.
This is an integrity checksum, not a digital signature or a registry approval.
The cumulative package changes when new evidence is appended; old run payloads
do not. Field deletion removes its monitoring records along with existing data.

## Crop benchmark

The benchmark accepts only single-crop seasons with current-version, sufficient
satellite coverage and accepted `crop_identity` observations sourced from a
field measurement or expert observation. Farmer reports, documents and simple
crop declarations do not independently qualify. Conflicting labels and
unknown/other crops are excluded with a reason. This is a software provenance
gate, not proof that an entered source was truthful.

For each season, the pipeline produces per-band medians, ranges and four
within-season temporal medians. Same-date optical granules are aggregated;
one dominant radar relative orbit is used. Field identifiers, declarations,
districts and labels are not input features. Missing-value imputation is fitted
within training folds. Models are Random Forest and XGBoost, with fixed seeds.

Evaluation supports held-out fields, years (season-start year) and districts.
Fields shared between train/test are always removed from training, including
for year splits. The benchmark refuses folds with no training fields or crops
absent from training. At least four eligible seasons and two crops are needed;
larger independent samples are required for meaningful conclusions. Overlapping
or adjacent fields can still be correlated: district holdout and independent
external evaluation remain important.

Results include per-class precision/recall/F1, confusion matrices, log loss,
multiclass Brier score, per-example probabilities, fold manifests, software
versions and the frozen dataset with its digest. Results persist as completed
jobs and can be reopened from **Saved comparisons**. No model is promoted into
production. Probabilities are not calibrated, and full-season features cannot
substantiate early-season predictions. No Bangladesh accuracy claim is made.

## Existing rice AI compatibility

`s1-linear-rvi-v2` fixes the old RVI calculation. Cache windows without this
version are treated as misses; old AI datasets require rebuilding and old
model bundles require retraining. They are not deleted or re-labelled as
current. The rice dataset builder uses only current-version caches. Rice
cross-validation now groups by field and requires all three training labels
in every fold. Its labels still come from the threshold gate; results remain
threshold agreement rather than independent AWD accuracy.

## Boundaries and next experiments

This pilot supplies multi-crop recordkeeping, observation collection and a
supervised benchmark. It does not implement multi-label crop identification,
automatic crop/practice deployment, weather fusion, a language-model assistant,
document extraction, uploaded photos, new carbon-methodology eligibility, or
digital soil mapping. Existing historical carbon exports retain their older
workflow; new monitoring snapshots are not yet linked to committed credits.
Generic monitoring does not run the rice AWD detector on non-rice crops.

Next, obtain independent local labels and compare the same frozen splits with
WorldCereal/Presto representations. Preserve required band/scaling/masking/
timestamp conventions and distinguish externally pretrained features from
local fine-tuning (which must occur inside training folds). Do not fabricate
foundation-model comparison results when embeddings or local labels are absent.
Then evaluate practice-specific models and propagation of observation uncertainty
into exploratory carbon estimates, separately from methodology-required deductions.

Research informing this design:

- [WorldCereal operational deployment, PMLR 2025](https://proceedings.mlr.press/v292/butsko25a.html)
- [WorldCereal source](https://github.com/WorldCereal/worldcereal-classification)
- [PromethEO model adapters](https://github.com/WorldCereal/prometheo)
- [SwissCrop25, August 2026 workshop paper](https://arxiv.org/abs/2608.09497)
- [Foundation Models Meet Agriculture, August 2026 preprint](https://arxiv.org/abs/2608.30392)
- [Cross-region agriculture benchmark, June 2026 preprint](https://arxiv.org/abs/2606.29664)
- [Digital soil mapping MRV, July 2026](https://www.nature.com/articles/s44264-026-00125-0)
- [Verra VT0014](https://verra.org/methodologies/vt0014-estimating-organic-carbon-stocks-using-digital-soil-mapping-v1-0/)

## Deployment and checks

The additive tables are created on application startup for SQLite/Postgres.
No existing crop data is guessed or rewritten as a season. Background collection
and evaluation use the application's existing in-process job runner; restart
recovery and durable external workers are not implemented in this pilot.
Earth Engine access is needed only for collection, not records or review.

Automated checks use isolated databases and synthetic examples. They test tenant
and role isolation, date/measurement constraints, independent review, immutable
run snapshots, cache compatibility, field-isolated folds and reproducibility.
They do not establish satellite or crop-classification accuracy.

```sh
venv/bin/python -m pytest tests/backend/ -q
venv/bin/python -m pytest tests/test_crop_benchmark.py tests/test_carbon_calculator.py tests/test_carbon_calculator_alm.py -q
cd frontend
npm run build
```
