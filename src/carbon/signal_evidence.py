"""Read-only signal evidence selection and snapshot provenance; never decides readiness."""
import json
import math
from sqlalchemy import text
from src.persistence.database import get_db_connection, get_job


# Only the rule-based detector may supply calculation inputs. The ML-baseline
# detectors (random_forest/xgboost) are trained on this detector's own output
# (src/ai/ml/dataset_builder.py), so their drydown counts are not independent
# evidence and must never reach a carbon calculation.
THRESHOLD_DETECTOR = "Threshold Gate (rule-based)"


def candidates_for_fields(org_id, field_ids):
    """candidates() for many fields in one query: {field_id: runs}."""
    field_ids = list(dict.fromkeys(field_ids))
    if not field_ids:
        return {}
    clauses = " OR ".join(f"payload_json LIKE :p{i}" for i in range(len(field_ids)))
    params = {"org": org_id, **{f"p{i}": f'%"field_id": {json.dumps(f)}%' for i, f in enumerate(field_ids)}}
    with get_db_connection() as conn:
        rows = conn.execute(text("SELECT job_id, finished_at, result_json FROM background_jobs WHERE org_id=:org "
                                 f"AND job_type='signal_run' AND status='done' AND ({clauses}) ORDER BY finished_at DESC"),
                            params).mappings().all()
    out = {f: [] for f in field_ids}
    for row in rows:
        result = json.loads(row['result_json'] or '{}')
        runs = out.get(result.get('field_id'))
        if runs is None or result.get('detector_used') != THRESHOLD_DETECTOR or len(runs) == 20:
            continue
        runs.append({"job_id": row['job_id'], "finished_at": str(row['finished_at']) if row['finished_at'] else None,
                     **{key: result.get(key) for key in ('window_start', 'window_end', 'area_ha', 'total_awd', 'season_length_days', 'detector_used', 'sowing_date', 'harvest_date')}})
    return out


def candidates(org_id, field_id):
    # No row LIMIT before the field filter: in a busy org an org-wide cap could
    # hide this field's runs entirely.
    # Prefilter on the small payload so only this field's (large) results are
    # transferred; the exact field check below still decides.
    pattern = f'%"field_id": {json.dumps(field_id)}%'
    with get_db_connection() as conn:
        rows = conn.execute(text("SELECT job_id, finished_at, result_json FROM background_jobs WHERE org_id=:org AND job_type='signal_run' AND status='done' AND payload_json LIKE :pattern ORDER BY finished_at DESC"), {"org": org_id, "pattern": pattern}).mappings().all()
    output = []
    for row in rows:
        result = json.loads(row['result_json'] or '{}')
        if result.get('field_id') != field_id or result.get('detector_used') != THRESHOLD_DETECTOR:
            continue
        output.append({"job_id": row['job_id'], "finished_at": str(row['finished_at']) if row['finished_at'] else None,
                       **{key: result.get(key) for key in ('window_start', 'window_end', 'area_ha', 'total_awd', 'season_length_days', 'detector_used', 'sowing_date', 'harvest_date')}})
        if len(output) == 20:
            break
    return output


def provenance(org_id, field, body, inputs):
    if not body.signal_run_id:
        return {"mode": "manual", "notice": "Inputs entered manually; no saved signal run linked."}
    if body.accounting_pathway != 'vm0051_rice_awd':
        raise ValueError('Signal input evidence is supported only for the rice AWD pathway.')
    job = get_job(org_id, body.signal_run_id)
    result = (job or {}).get('result') or {}
    if not job or job['job_type'] != 'signal_run' or job['status'] != 'done' or result.get('field_id') != field['field_id']:
        raise ValueError('Saved signal evidence is unavailable on this field.')
    if result.get('detector_used') != THRESHOLD_DETECTOR:
        raise ValueError('Only rule-based (Threshold Gate) signal runs can supply calculation inputs; '
                         'ML-baseline detector runs are trained on that detector\'s own output.')
    if result.get('window_start') != body.monitoring_period_start.isoformat() or result.get('window_end') != body.monitoring_period_end.isoformat():
        raise ValueError('Saved signal evidence must match both monitoring dates exactly.')
    try:
        same_area = math.isclose(float(result['area_ha']), float(field['area_ha']), rel_tol=1e-9, abs_tol=1e-9)
    except (KeyError, TypeError, ValueError):
        same_area = False
    if not same_area:
        raise ValueError('Saved signal evidence does not match the registered field area.')
    values = {"awd_events": result.get('total_awd'), "season_length_days": result.get('season_length_days')}
    if any(value is None for value in values.values()):
        raise ValueError('Saved signal evidence is missing calculation inputs.')
    return {"mode": "saved_signal", "job_id": job['job_id'], "finished_at": str(job.get('finished_at') or ''),
            "window_start": result['window_start'], "window_end": result['window_end'], "detector": result.get('detector_used'),
            "source_values": values, "overridden_inputs": [key for key, value in values.items() if inputs.get(key) != value],
            "notice": "Field, period and area matched. The legacy signal job does not freeze a field-boundary or crop-season version; confirm those before use. Other inputs remain manual."}
