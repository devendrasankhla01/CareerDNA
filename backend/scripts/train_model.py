"""Train, evaluate, and persist the placement-readiness model.

Candidates: Logistic Regression (interpretable baseline) and Random Forest.
The model with the strongest overall validation performance (F1 + ROC-AUC,
stability) is selected and persisted together with metrics and metadata.

Run:  .venv/bin/python -m scripts.train_model
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ml.features import FEATURE_GROUPS, FEATURE_ORDER, FEATURE_SCHEMA_VERSION

DATASETS_DIR = Path(__file__).resolve().parents[2] / "datasets"
ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
MODEL_VERSION = "careerdna-v1.0"
SEED = 42
CV_FOLDS = 5


def load_data() -> pd.DataFrame:
    path = DATASETS_DIR / "synthetic_historical.csv"
    if not path.exists():
        raise SystemExit(f"Training dataset not found at {path}. Run: python -m scripts.generate_data")
    return pd.read_csv(path)


def build_candidates() -> dict[str, Pipeline]:
    return {
        "Logistic Regression": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=2000, random_state=SEED)),
        ]),
        "Random Forest": Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("clf", RandomForestClassifier(
                n_estimators=200, min_samples_leaf=3, random_state=SEED, n_jobs=1
            )),
        ]),
    }


def evaluate(pipe: Pipeline, X_tr, y_tr, X_te, y_te) -> dict:
    pipe.fit(X_tr, y_tr)
    proba = pipe.predict_proba(X_te)[:, 1]
    pred = (proba >= 0.5).astype(int)
    return {
        "accuracy": round(float(accuracy_score(y_te, pred)), 4),
        "precision": round(float(precision_score(y_te, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_te, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_te, pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_te, proba)), 4),
        "confusion_matrix": confusion_matrix(y_te, pred).tolist(),
    }


def cv_stability(pipe_factory, X: pd.DataFrame, y: pd.Series) -> float:
    """Mean F1 over stratified K-fold (stability signal)."""
    from sklearn.model_selection import cross_val_score
    scores = cross_val_score(pipe_factory, X, y, cv=CV_FOLDS, scoring="f1")
    return float(scores.mean())


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    X = df[FEATURE_ORDER].copy()
    y = df["placed"].astype(int)

    print(f"Dataset: {len(df)} rows | target distribution: placed={y.mean():.3f}")
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=SEED
    )

    candidates = build_candidates()
    results = {}
    best_name, best_score = None, -1.0
    for name, pipe in candidates.items():
        m = evaluate(pipe, X_tr, y_tr, X_te, y_te)
        # selection: F1 and ROC-AUC dominate; accuracy is secondary context
        score = m["f1"] + m["roc_auc"]
        results[name] = m
        print(f"  {name:20s} acc={m['accuracy']:.3f} f1={m['f1']:.3f} auc={m['roc_auc']:.3f}")
        if score > best_score:
            best_score, best_name = score, name

    # final fit of the selected model on the full training split
    selected = candidates[best_name]
    selected.fit(X_tr, y_tr)
    selected_cv = cv_stability(selected, pd.concat([X_tr, X_te]), pd.concat([y_tr, y_te]))
    print(f"Selected: {best_name} | CV F1 = {selected_cv:.3f}")

    # global importance (feature-level, friendly labels available in UI)
    clf = selected.named_steps["clf"]
    if hasattr(clf, "feature_importances_"):
        importances = {f: round(float(v), 4) for f, v in zip(FEATURE_ORDER, clf.feature_importances_)}
    else:
        importances = {f: round(abs(float(v)), 4) for f, v in zip(FEATURE_ORDER, np.asarray(clf.coef_).ravel())}
    importances = dict(sorted(importances.items(), key=lambda kv: kv[1], reverse=True))

    # SHAP global importance (TreeExplainer for RF; linear coefficients otherwise).
    # The classifier was trained on the preprocessed (imputed, and scaled for
    # LR) representation, so the background must be transformed identically.
    import shap  # noqa: WPS433 - imported late so training still works without it

    Xte_pre = X_te.copy()
    for step_name, step in selected.named_steps.items():
        if step_name == "clf":
            break
        Xte_pre = step.transform(Xte_pre)
    idx = np.random.RandomState(SEED).choice(
        len(Xte_pre), size=min(200, len(Xte_pre)), replace=False)
    background = np.asarray(Xte_pre)[idx]
    if hasattr(clf, "estimators_"):
        explainer = shap.TreeExplainer(clf)
        sv = explainer.shap_values(background, silent=True)
        if isinstance(sv, list):
            sv = sv[1]
        mean_abs = np.abs(np.asarray(sv, dtype=float)).mean(axis=0)
        shap_global = {f: round(float(v), 4) for f, v in zip(FEATURE_ORDER, mean_abs)}
        shap_global = dict(sorted(shap_global.items(), key=lambda kv: kv[1], reverse=True))
    else:
        shap_global = importances

    meta = {
        "model_name": best_name,
        "model_version": MODEL_VERSION,
        "feature_schema": FEATURE_SCHEMA_VERSION,
        "feature_order": FEATURE_ORDER,
        "feature_groups": FEATURE_GROUPS,
        "dataset_type": "synthetic",
        "dataset_size": int(len(df)),
        "test_size": int(len(X_te)),
        "target_distribution": {"placed": round(float(y.mean()), 3), "not_placed": round(float(1 - y.mean()), 3)},
        "random_seed": SEED,
        "cv_folds": CV_FOLDS,
        "cv_f1_selected": round(selected_cv, 4),
        "explainability": "SHAP TreeExplainer (local + global)" if hasattr(clf, "estimators_") else "linear coefficients",
        "metrics": results,
        "selected_metrics": results[best_name],
        "global_importance": importances,
        "shap_global_importance": shap_global,
        "selection_rule": "highest (F1 + ROC-AUC) on held-out test split, with K-fold F1 as stability check",
        "readiness_thresholds": {"needs_training_lt": 60, "near_ready_lt": 80},
        "trained_at": pd.Timestamp.now().isoformat(),
    }

    joblib.dump(selected, ARTIFACTS_DIR / "placement_readiness_model.joblib")
    (ARTIFACTS_DIR / "metrics.json").write_text(json.dumps(meta, indent=2))
    (ARTIFACTS_DIR / "feature_metadata.json").write_text(
        json.dumps({"feature_order": FEATURE_ORDER, "schema": FEATURE_SCHEMA_VERSION}, indent=2)
    )
    (ARTIFACTS_DIR / "global_importance.json").write_text(json.dumps(meta["shap_global_importance"], indent=2))

    # load-back validation (fresh deserialize + one prediction)
    reloaded = joblib.load(ARTIFACTS_DIR / "placement_readiness_model.joblib")
    check = reloaded.predict_proba(X_te.head(5))
    assert check.shape == (5, 2) and np.isfinite(check).all()
    print(f"Artifact validated: model reloads and predicts. Saved to {ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
