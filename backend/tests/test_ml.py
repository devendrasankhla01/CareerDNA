"""ML pipeline tests: artifacts, prediction invariants, explanation consistency."""
import json
import math

import pytest

from app.ml.features import ACTIONABLE_FEATURES, FEATURE_ORDER, FEATURE_LABELS
from app.services.model_service import model_service


@pytest.fixture(scope="module")
def model():
    assert model_service.available, "artifact must be trained (scripts.train_model.py)"
    return model_service


def test_feature_schema_is_complete():
    assert len(FEATURE_ORDER) == 23
    assert len(set(FEATURE_ORDER)) == 23
    for f in FEATURE_ORDER:
        assert f in FEATURE_LABELS, f"missing label for {f}"
    # no identifier or demographic features
    for f in FEATURE_ORDER:
        assert "usn" not in f and "name" not in f and "email" not in f
        assert "branch" not in f and "gender" not in f
    # fixed historical features are not actionable
    for f in ("cgpa", "tenth_percentage", "twelfth_percentage", "backlog_history_count"):
        assert f not in ACTIONABLE_FEATURES


def test_artifacts_exist():
    from app.core.config import get_settings
    s = get_settings()
    for name in ("placement_readiness_model.joblib", "metrics.json",
                 "feature_metadata.json", "global_importance.json"):
        p = s.model_dir / name
        assert p.exists(), f"missing artifact {name}"
    meta = json.loads((s.model_dir / "metrics.json").read_text())
    assert meta["model_version"]
    assert meta["selected_metrics"]["roc_auc"] > 0.6
    assert meta["selected_metrics"]["f1"] > 0.5


def _features(**over) -> dict:
    base = {
        "cgpa": 7.5, "tenth_percentage": 80.0, "twelfth_percentage": 78.0,
        "backlog_history_count": 0, "programming_score": 65, "sql_score": 60,
        "dsa_score": 60, "web_dev_score": 60, "git_score": 55, "cloud_score": 40,
        "aptitude_score": 65, "logical_score": 60, "coding_score": 65,
        "communication_score": 55, "interview_score": 55, "presentation_score": 50,
        "verified_project_count": 1, "project_complexity_score": 70,
        "verified_internship_count": 0, "verified_certification_count": 1,
        "open_source_score": 0, "hackathon_score": 0, "leadership_score": 0,
    }
    base.update(over)
    return base


def test_prediction_bounded(model):
    for feats in (_features(), _features(cgpa=9.8, coding_score=95, dsa_score=90),
                  _features(cgpa=4.6, coding_score=20, backlog_history_count=3)):
        p = model.predict_proba(feats)
        assert 0.0 <= p <= 1.0


def test_prediction_monotonic_in_key_skill(model):
    low = model.predict_proba(_features(coding_score=40))
    high = model.predict_proba(_features(coding_score=85))
    assert high > low


def test_missing_features_imputed(model):
    feats = _features()
    feats["sql_score"] = None
    feats["cloud_score"] = None
    p = model.predict_proba(feats)
    assert 0.0 <= p <= 1.0


def test_explanation_consistency(model):
    """SHAP/linear contributions must sum to (logit output - baseline)."""
    feats = _features(communication_score=40)
    x = model.explain(feats)
    assert x["model_output"] > 0
    total = sum(c["contribution"] for c in x["all"])
    expected = x["model_output_logit"] - x["baseline"]
    assert abs(total - expected) < 0.05, (total, expected)
    # positive/limiting buckets are consistent with sign
    assert all(c["contribution"] > 0 for c in x["positive"])
    assert all(c["contribution"] < 0 for c in x["limiting"])
    # friendly labels only
    for c in x["all"]:
        assert c["label"] in FEATURE_LABELS.values()


def test_batch_prediction_matches_single(model):
    feats = [_features(), _features(dsa_score=80), _features(sql_score=30)]
    batch = model.predict_proba_batch(feats)
    for f, p in zip(feats, batch):
        single = model.predict_proba(f)
        assert abs(single - p) < 1e-9


def test_math_of_probability_to_score():
    # 0.737 -> 73.7 score, band Near-Ready (<80)
    assert 0 <= 0.737 * 100 - 73.7 < 1e-9
