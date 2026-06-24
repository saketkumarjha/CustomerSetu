"""
Smoke test for the incident scorer.
Run from the backend/ folder:

    python test_scorer.py

Expected output: a dict with risk_score, alert_priority, departments, top_drivers.
If you see "model_not_loaded", run:  pip install lightgbm scikit-learn shap pandas joblib
"""
import sys
from pathlib import Path

# Allow running directly without installing the app as a package
sys.path.insert(0, str(Path(__file__).parent))

from app.services.incident_scorer import score_cluster, _MODEL_LOADED

if not _MODEL_LOADED:
    print("\n❌  Model failed to load — check the error above and run:")
    print("    pip install lightgbm scikit-learn shap pandas joblib\n")
    sys.exit(1)

# ── Test 1: High-risk APK fraud cluster ──────────────────────────────────────
demo_high = {
    "event_type":                 "apk_fraud",
    "complaints_1h":              4,
    "complaints_6h":              7,
    "complaints_24h":             9,
    "distinct_customers_1h":      4,
    "distinct_customers_6h":      7,
    "distinct_customers_24h":     8,
    "velocity_ratio":             3.4,
    "channel_diversity":          3,
    "avg_severity":               4.0,
    "max_severity":               5,
    "avg_urgency":                7.5,
    "max_urgency":                9.0,
    "negative_sentiment_ratio":   0.85,
    "financial_loss_ratio":       0.70,
    "duplicate_ratio":            0.10,
    "rbi_reportable_ratio":       0.70,
    "min_complaints_met":         True,
}

# ── Test 2: Below evidence floor (should return scored=False) ─────────────────
demo_low = {
    "event_type":             "upi_payment_failure",
    "distinct_customers_24h": 1,          # below MIN_DISTINCT=2
    "min_complaints_met":     False,
}

print("\n── Test 1: High-risk APK fraud cluster ──────────────────────────────")
result = score_cluster(demo_high)
import json
print(json.dumps(result, indent=2))

print("\n── Test 2: Below evidence floor ─────────────────────────────────────")
result2 = score_cluster(demo_low)
print(json.dumps(result2, indent=2))

print("\n✅  Smoke test complete — model is correctly embedded in the backend.\n")
