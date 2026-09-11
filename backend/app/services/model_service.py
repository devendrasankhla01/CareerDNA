"""ML model service: artifact loading, prediction, and SHAP explanations.

The pipeline (imputer + classifier) is trained separately
(scripts/train_model.py) and loaded once at app startup. Inference always
goes through the same persisted pipeline — no manual preprocessing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.ml.features import FEATURE_LABELS, FEATURE_ORDER, FEATURE_SCHEMA_VERSION

MODEL_FILE = "placement_readiness_model.joblib"
METRICS_FILE = "metrics.json"


class ModelService:
    def __init__(self) -> None:
        self.pipeline = None
        self.meta: dict[str, Any] = {}
        self.error: str | None = None
        self._explainer = None

    def _preprocessed(self, X: np.ndarray) -> np.ndarray:
        """Apply every pipeline step before the final classifier, so that
        SHAP operates in the exact space the model was trained in."""
        out = X
        for name, step in self.pipeline.named_steps.items():
            if name == "clf":
                break
            out = step.transform(out)
        return out

    def load(self) -> bool:
        s = get_settings()
        path = Path(s.model_dir) / MODEL_FILE
        try:
            import joblib
            self.pipeline = joblib.load(path)
            self._explainer = None
            meta_path = Path(s.model_dir) / METRICS_FILE
            self.meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            self.error = None
            return True
        except Exception as e:  # pragma: no cover
            self.error = f"model artifact could not be loaded: {e}"
            self.pipeline = None
            return False

    @property
    def available(self) -> bool:
        return self.pipeline is not None

    @property
    def version(self) -> str:
        return self.meta.get("model_version", "unknown")

    def _matrix(self, features: dict[str, float | None]) -> "pd.DataFrame":
        import pandas as pd
        row = [features.get(name) for name in FEATURE_ORDER]
        return pd.DataFrame([row], columns=FEATURE_ORDER)

    def _matrix_batch(self, feature_dicts: list[dict[str, float | None]]) -> "pd.DataFrame":
        import pandas as pd
        rows = [[fd.get(name) for name in FEATURE_ORDER] for fd in feature_dicts]
        return pd.DataFrame(rows, columns=FEATURE_ORDER)

    def predict_proba(self, features: dict[str, float | None]) -> float:
        if not self.available:
            raise RuntimeError("Readiness model is not available")
        proba = self.pipeline.predict_proba(self._matrix(features))
        p = float(proba[0][1])
        if not np.isfinite(p):
            raise RuntimeError("Model returned a non-finite probability")
        return min(max(p, 0.0), 1.0)

    def predict_proba_batch(self, feature_dicts: list[dict[str, float | None]]) -> np.ndarray:
        """Vectorized inference (TPO cohort simulations)."""
        if not self.available or not feature_dicts:
            return np.array([])
        return self.pipeline.predict_proba(self._matrix_batch(feature_dicts))[:, 1]

    def explain(self, features: dict[str, float | None]) -> dict:
        """Local SHAP explanation with friendly labels.

        Contributions are in the model's native log-odds space (they sum to
        model_output_logit - baseline). Sign and relative magnitude are what
        the UI uses to separate "what's helping" from "what's limiting".

        Returns {positive: [...], limiting: [...], baseline, model_output,
        all: [{feature, label, value, contribution, direction}]}
        """
        if not self.available:
            raise RuntimeError("Readiness model is not available")
        clf = self.pipeline.named_steps["clf"]
        X = self._matrix(features)
        Xp = np.asarray(self._preprocessed(X), dtype=float)
        proba = float(self.pipeline.predict_proba(X)[0][1])

        if hasattr(clf, "estimators_"):
            try:
                import shap
                if self._explainer is None:
                    self._explainer = shap.TreeExplainer(clf)
                sv = self._explainer.shap_values(Xp, silent=True)
                if isinstance(sv, list):
                    sv = sv[1]
                values = np.asarray(sv, dtype=float)[0]
                ev = np.asarray(self._explainer.expected_value, dtype=float)
                baseline = float(ev.ravel()[0]) if ev.size else 0.0
            except ImportError:
                values = np.zeros(len(FEATURE_ORDER))
                baseline = 0.0
        else:  # linear model: exact additive contributions (log-odds space)
            coef = np.asarray(clf.coef_).ravel()
            values = coef * Xp[0]
            try:
                baseline = float(np.asarray(clf.intercept_).ravel()[0])
            except Exception:
                baseline = 0.0

        filled = Xp[0]
        contribs = []
        for i, name in enumerate(FEATURE_ORDER):
            v = float(values[i])
            contribs.append({
                "feature": name,
                "label": FEATURE_LABELS.get(name, name),
                "value": None if features.get(name) is None else round(float(filled[i]), 1),
                "contribution": round(v, 4),
                "direction": "positive" if v >= 0 else "negative",
            })
        contribs.sort(key=lambda c: abs(c["contribution"]), reverse=True)

        def bucket(c: dict) -> str:
            a = abs(c["contribution"])
            return "High" if a >= 0.3 else ("Moderate" if a >= 0.12 else "Low")

        positive = [{**c, "impact": bucket(c)} for c in contribs
                    if c["direction"] == "positive" and abs(c["contribution"]) > 1e-6][:4]
        limiting = [{**c, "impact": bucket(c)} for c in contribs
                    if c["direction"] == "negative" and abs(c["contribution"]) > 1e-6][:4]
        p = min(max(proba, 1e-6), 1 - 1e-6)
        return {
            "baseline": round(baseline, 4),
            "model_output": round(proba, 4),
            "model_output_logit": round(float(np.log(p / (1 - p))), 4),
            "positive": positive,
            "limiting": limiting,
            "all": contribs,
        }


model_service = ModelService()
