from fastapi import APIRouter, Depends
from pathlib import Path

from app.core.config import get_settings
from app.ml.features import FEATURE_GROUPS, FEATURE_LABELS, FEATURE_ORDER
from app.models import User
from app.services.auth_service import get_current_user
from app.services.model_service import MODEL_FILE, model_service

router = APIRouter(prefix="/api/model", tags=["model"])


@router.get("/info")
def info(user: User = Depends(get_current_user)):
    s = get_settings()
    meta = model_service.meta if model_service.available else {}
    out = {
        "status": "ok" if model_service.available else "model_unavailable",
        "available": model_service.available,
        "model_version": model_service.version,
        "model_name": meta.get("model_name"),
        "model_file": str(Path(s.model_dir) / MODEL_FILE),
        "metrics": meta.get("metrics", {}),
        "selected_metrics": meta.get("selected_metrics", {}),
        "cv_f1": meta.get("cv_f1_selected"),
        "selection_rule": meta.get("selection_rule"),
        "selection": meta.get("selection", {}),
        "feature_count": len(FEATURE_ORDER),
        "features": [
            {"name": n, "label": FEATURE_LABELS.get(n, n)} for n in FEATURE_ORDER
        ],
        "feature_groups": FEATURE_GROUPS,
        "disclaimer": (
            "CareerDNA predicts placement readiness, not placement outcomes. "
            "Scores are model-estimated from your verified profile and can change as your "
            "profile is verified and updated. This is a readiness signal, not a hiring guarantee."
        ),
    }
    if model_service.available:
        import json
        gi_path = Path(s.model_dir) / "global_importance.json"
        if gi_path.exists():
            out["global_importance"] = json.loads(gi_path.read_text())
    return out
