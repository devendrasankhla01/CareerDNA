"""CareerDNA API — FastAPI application."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, documents, faculty, model_info, placement, student, tpo
from app.core.config import get_settings
from app.db.mongo import check_mongo_status
from app.db.session import Base, engine
from app.models import User  # noqa: F401  (register models)
from app.services.model_service import model_service

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("careerdna")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    loaded = model_service.load()
    if loaded:
        logger.info("Readiness model loaded: %s", model_service.version)
    else:
        logger.warning("Readiness model NOT loaded: %s", model_service.error)
    # ensure reference data exists (idempotent)
    from app.services import reference_service
    reference_service.ensure_reference_data()
    logger.info("CareerDNA API ready (demo_mode=%s)", get_settings().demo_mode)
    yield


app = FastAPI(
    title="CareerDNA — AI Placement Predictor",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

s = get_settings()
origins = [s.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"]
if s.frontend_origin == "*":
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if "*" in origins else origins,
    allow_origin_regex=r"https://.*\.vercel\.app" if "*" not in origins else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(student.router)
app.include_router(faculty.router)
app.include_router(tpo.router)
app.include_router(model_info.router)
app.include_router(placement.router)
app.include_router(documents.router)


@app.get("/api/health")
def health():
    from app.db.session import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        db.close()
    return {
        "status": "ok",
        "database": "ok" if db_ok else "error",
        "mongodb": check_mongo_status(),
        "model": model_service.version if model_service.available else "not_loaded",
        "demo_mode": s.demo_mode,
    }
