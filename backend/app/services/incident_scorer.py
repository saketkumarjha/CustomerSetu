# backend/app/services/incident_scorer.py
"""
Incident Scorer
===============
Loads the trained LightGBM model from the predictiveComplaintIntellegence folder
and scores complaint_clusters rows that have hit the evidence gate.

The models directory is resolved relative to THIS file so it works regardless
of where uvicorn is launched from:

    backend/
    ├── app/
    │   └── services/
    │       └── incident_scorer.py   ← __file__
    └── predictiveComplaintIntellegence/
        ├── incident_model.pkl
        ├── calibrator.pkl
        ├── feature_cols.json
        └── routing_table.json
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Resolve models directory (3 levels up from this file → backend root) ──────
# __file__  = .../backend/app/services/incident_scorer.py
# .parent   = .../backend/app/services/
# .parent   = .../backend/app/
# .parent   = .../backend/
_MODELS_DIR = Path(__file__).parent.parent.parent / "predictiveComplaintIntellegence"

# ── Lazy-load guard — only import heavy libs when the module is actually used ──
try:
    import joblib
    import pandas as pd
    import shap

    _model        = joblib.load(_MODELS_DIR / "incident_model.pkl")
    _calibrator   = joblib.load(_MODELS_DIR / "calibrator.pkl")
    _feature_cols = json.loads((_MODELS_DIR / "feature_cols.json").read_text())
    _routing      = json.loads((_MODELS_DIR / "routing_table.json").read_text())
    _explainer    = shap.TreeExplainer(_model)

    ROUTING_TABLE       = _routing["routing"]
    DEFAULT_DEPARTMENTS = _routing["default"]

    _MODEL_LOADED = True
    logger.info("[SCORER] Incident model loaded from %s", _MODELS_DIR)

except Exception as _load_err:
    _MODEL_LOADED = False
    logger.error(
        "[SCORER] Failed to load incident model — scoring will be skipped. "
        "Run: pip install lightgbm scikit-learn shap pandas joblib\nError: %s",
        _load_err,
    )

# ── Constants ─────────────────────────────────────────────────────────────────
MIN_DISTINCT = 2   # must match cluster_builder._MIN_COMPLAINTS_TO_SCORE


def _alert_priority(prob: float, rbi_ratio: float = 0.0) -> str:
    if prob >= 0.80 or (prob >= 0.65 and rbi_ratio >= 0.5):
        return "critical"
    if prob >= 0.60:
        return "high"
    if prob >= 0.40:
        return "medium"
    return "low"


def score_cluster(snapshot: dict) -> dict:
    """
    Score a single cluster snapshot.

    Returns a dict with:
        scored (bool)               — False if below evidence floor or model not loaded
        risk_score (float | None)   — 0–100
        growth_probability (float)  — 0.0–1.0
        alert_priority (str)        — "low" | "medium" | "high" | "critical"
        departments (list[str])
        confidence_score (float)    — 0.0–1.0
        predicted_impact_customers (int)
        top_drivers (list[dict])    — top 5 SHAP contributors
    """
    if not _MODEL_LOADED:
        return {
            "scored": False,
            "reason": "model_not_loaded",
            "risk_score": None,
            "alert_priority": None,
            "departments": None,
        }

    dc24 = snapshot.get("distinct_customers_24h", 0) or 0
    if dc24 < MIN_DISTINCT:
        return {
            "scored": False,
            "reason": "below_evidence_floor",
            "risk_score": None,
            "alert_priority": None,
            "departments": None,
        }

    # Build feature row — missing features default to 0 (safe for tree models)
    row = pd.DataFrame([{c: snapshot.get(c, 0) for c in _feature_cols}])[_feature_cols]

    # Support both LightGBM Booster (predict returns raw scores/probs)
    # and sklearn-wrapped LGBMClassifier (predict_proba).
    import lightgbm as lgb
    if isinstance(_model, lgb.Booster):
        # Booster.predict() returns probability of positive class directly
        raw_prob = float(_model.predict(row.values)[0])
    else:
        raw_prob = float(_model.predict_proba(row)[0][1])

    # Calibrator: IsotonicRegression uses transform() in older sklearn builds
    # but predict() in newer ones. Support both.
    try:
        prob = float(_calibrator.predict([raw_prob])[0])
    except AttributeError:
        prob = float(_calibrator.transform([raw_prob])[0])
    prob = max(0.0, min(1.0, prob))   # clamp to [0, 1]

    # SHAP explanations — handle Booster vs sklearn wrapper differences
    try:
        sv = _explainer.shap_values(row)
        sv_row = sv[1] if isinstance(sv, list) else sv
        sv_values = sv_row[0] if hasattr(sv_row[0], '__iter__') else sv_row
        contribs = sorted(
            zip(_feature_cols, sv_values),
            key=lambda x: abs(x[1]),
            reverse=True,
        )
        top_drivers = [
            {
                "feature":      f,
                "direction":    "raises" if v > 0 else "lowers",
                "contribution": round(float(v), 3),
            }
            for f, v in contribs[:5]
        ]
    except Exception:
        logger.warning("[SCORER] SHAP explanation failed — returning empty top_drivers")
        top_drivers = []

    et  = snapshot.get("event_type", "unknown")
    rbi = snapshot.get("rbi_reportable_ratio", 0.0) or 0.0

    return {
        "scored":                     True,
        "risk_score":                 round(prob * 100, 1),
        "growth_probability":         round(prob, 4),
        "alert_priority":             _alert_priority(prob, rbi),
        "departments":                ROUTING_TABLE.get(et, DEFAULT_DEPARTMENTS),
        "confidence_score":           round(min(1.0, dc24 / 10.0), 2),
        "predicted_impact_customers": int(dc24 * max(1, round(prob * 5))),
        "top_drivers":                top_drivers,
    }