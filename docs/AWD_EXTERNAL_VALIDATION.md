# Independent AWD research benchmark (experimental)

## Scope and status

This is a **shadow-mode research experiment**, not an AWD-event ground-truth
validator or a carbon-calculation component. No existing calculation,
readiness or issuance code has been changed.

- Existing GEE extractor: `src/signals/earth_engine.py`.
- Existing statistical drydown detector: `src/signals/threshold_gate.py`.
- Existing pseudo-labeled rice ML: `src/ai/ml/dataset_builder.py`.
- Separate externally labeled research baseline: `src/ai/ml/external_awd.py`.
- Offline operator command: `scripts/train_external_awd.py`.
- Read-only endpoint: `GET /fields/{field_id}/awd-external-comparison`.
- UI: Field → **AWD Validation** (rice fields only).

## Source and crucial label distinction

Research source: [Microsoft Ricemapper](https://github.com/microsoft/rice-irrigation-mapping-s1s2),
based on The Nature Conservancy PRANA plots from Punjab, India, Kharif 2024.

The published training code for task `AWD` maps original
`AWD → 1`, and `PTR, DSR → 0`. We preserve this exact target and describe it
as **AWD versus the published non-AWD research categories**.
Although the model card discusses AWD versus continuous flooding, the released
training script's negative class is based on sowing categories, not an explicitly
verified CF water-state or independent AWD drydown count. Do **not** claim a
measured AWD-versus-CF confusion matrix without resolving the original label
semantics with the dataset authors.

The publicly released research features are de-identified. Original polygons
and in-situ event time series cannot be reconstructed from this release.

## Obtaining and training on REAL research features

The researcher README describes the features archive in `data/` (extract with
`tar -xJf dataset_features.tar.xz`), creating directories with parquet files,
usually under `data/features/`. It also mentions paths under
`ricemapper/dataset/features/`; inspect the actual downloaded archive rather
than assuming a path. Do not use the synthetic AWD CSV for this experiment.

Start with the handcrafted **HC** features for the AWD date window
(May 1–December 15, 2024). This avoids requiring Presto embeddings locally.
Select the correct AWD feature parquet and inspect its schema first.

Install application requirements and parquet support:

```bash
pip install -r requirements.txt
pip install pyarrow
```

Inspect available files:

```bash
find data/features -name '*.parquet' | sort
python -c "import pandas as pd,sys; f=pd.read_parquet(sys.argv[1]); print(f.shape); print(f.columns.tolist()); print(f['label'].value_counts())" /path/to/train_HC.parquet
```

Training, with a de-identified research feature file actually downloaded from
the authors' repository:

```bash
python scripts/train_external_awd.py \
  --input /path/to/train_HC.parquet \
  --output data/external_awd_benchmark
```

If the research parquet provides a **stable unique plot ID**, supply
`--group-column <column>` (or use a supported auto-detected identifier).
Otherwise the trainer uses a stratified row holdout and **explicitly labels
plot-independence unverified**. Do not present row-holdout metrics as
independent-field validation. Rows from nearby or related plots can be
correlated even with unique IDs.

Outputs:
- `data/external_awd_benchmark/metrics.json`: split, performance, confusion
  matrix, limitations, source SHA-256, and feature names.
- `data/external_awd_benchmark/model.joblib`: isolated research model.
  Never load untrusted user-supplied joblib files.

The existing FastAPI deployment reads only **metrics.json**. Data and model
files are not checked into Git. On separately hosted backend deployments, the
operator must explicitly provision metrics.json to the backend's configured
`DATA_DIR` location; a local training run will not magically make metrics
appear on Render.

## Model limitations and deployment gate

**Current inference is intentionally disabled** for real Terra Audit fields.
The independent model is *not* registered as a choice in Signal Analytics.

Published source processing uses calibrated gamma0, plot-mean aggregation
and matched date-window handcrafted features. Terra Audit's current
`src/signals/earth_engine.py` fetches `COPERNICUS/S1_GRD` and applies a
field-median aggregation. Its existing `vv`, `vh`, `cross_ratio` and
`rvi` features cannot be safely relabeled or reindexed to make them
equivalent to Ricemapper HC inputs.

Before enabling field-level predictions:
1. Reproduce the research feature schema, calibration, orbit, aggregation,
   imputation, scaling and temporal window with verified test fixtures.
2. Confirm the original dataset's irrigation label semantics. Do not call PTR
   or DSR identical to measured continuous flooding.
3. Validate the adapted model on independently observed Bangladesh rice plots,
   preferably multiple fields, farms, seasons and districts.
4. Separately evaluate the **0 / 1 / 2+ true drydown count** and induced
   VM0051 water-scaling category with paired in-situ water-level observations.
5. Review the methodology's rules for satellite-derived monitoring inputs
   and account for uncertainty conservatively.

No experimental output changes `src/carbon/rice.py`, the detector used for
credits, or the issuance/readiness modules.

## Running tests

```bash
pytest tests/test_external_awd.py -q
pytest tests/test_carbon_calculator.py -q
pytest tests/backend/ -q
cd frontend && npx tsc --noEmit && npm run build
```

The external benchmark test uses synthetic **test fixtures only** to check
label handling and leakage-safe splitting; it is not a measured research
performance result. Never substitute these fixture metrics for real-world ML
accuracy.

For the academic presentation, cite:
Shah et al. (2025), *Remote Sensing Reveals Adoption of Sustainable Rice
Farming Practices Across Punjab, India*,
https://arxiv.org/abs/2507.08605.
