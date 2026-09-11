"""MongoDB connection manager, document storage, and activity logging.

CareerDNA uses a dual-engine data model:
1. Relational Database (SQLite / PostgreSQL via SQLAlchemy) for ACID transactions,
   institutional criteria matching, student profiles, and placement pipelines.
2. MongoDB (via PyMongo) for flexible document storage:
   - Student rich resumes & external portfolios
   - Project deep-dive documentation & GitHub metadata
   - Institutional cross-dashboard audit & activity streams
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, PyMongoError

from app.core.config import get_settings

logger = logging.getLogger("careerdna.mongo")

_client: MongoClient | None = None
_in_memory_activity_fallback: list[dict[str, Any]] = []
_in_memory_docs_fallback: dict[str, dict[str, Any]] = {}


def get_mongo_client() -> MongoClient | None:
    """Get or initialize singleton MongoClient."""
    global _client
    if _client is not None:
        return _client

    settings = get_settings()
    url = (settings.mongodb_url or "").strip()
    if not url:
        return None

    try:
        # serverSelectionTimeoutMS=2000 prevents blocking if offline
        _client = MongoClient(url, serverSelectionTimeoutMS=2000, connectTimeoutMS=2000)
        # Test connection
        _client.admin.command("ping")
        logger.info("Connected to MongoDB successfully at %s", settings.mongodb_db_name)
        return _client
    except (ConnectionFailure, PyMongoError, Exception) as exc:
        logger.warning("MongoDB not reachable (%s). Falling back to resilient mode.", exc)
        _client = None
        return None


def get_mongo_db() -> Database | None:
    """Get MongoDB database instance."""
    client = get_mongo_client()
    if client is None:
        return None
    settings = get_settings()
    return client[settings.mongodb_db_name]


def check_mongo_status() -> dict[str, Any]:
    """Check live MongoDB connectivity status for /api/health."""
    settings = get_settings()
    url = (settings.mongodb_url or "").strip()
    if not url:
        return {"status": "unconfigured", "message": "MONGODB_URL not set (in-memory mode)"}

    client = get_mongo_client()
    if client is None:
        return {"status": "disconnected", "message": "Could not connect to MongoDB"}

    try:
        client.admin.command("ping")
        return {"status": "connected", "database": settings.mongodb_db_name}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def get_student_documents_collection() -> Collection | None:
    db = get_mongo_db()
    if db is None:
        return None
    return db["student_documents"]


def get_activity_logs_collection() -> Collection | None:
    db = get_mongo_db()
    if db is None:
        return None
    return db["activity_logs"]


# ---------------------------------------------------------------- Activity Logging
def log_activity(
    action: str,
    actor_id: int | str | None,
    actor_role: str,
    target_type: str | None = None,
    target_id: int | str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Log an event across the Student-HOD-TPO-Company pipeline into MongoDB."""
    now = datetime.now(timezone.utc)
    entry = {
        "action": action,
        "actor_id": str(actor_id) if actor_id is not None else None,
        "actor_role": actor_role,
        "target_type": target_type,
        "target_id": str(target_id) if target_id is not None else None,
        "details": details or {},
        "timestamp": now.isoformat(),
        "created_at": now,
    }

    try:
        col = get_activity_logs_collection()
        if col is not None:
            res = col.insert_one(entry)
            entry["_id"] = str(res.inserted_id)
        else:
            _in_memory_activity_fallback.insert(0, entry)
            if len(_in_memory_activity_fallback) > 500:
                _in_memory_activity_fallback.pop()
    except Exception as exc:
        logger.warning("Failed to write activity to MongoDB: %s", exc)
        _in_memory_activity_fallback.insert(0, entry)

    return entry


def get_activity_logs(
    limit: int = 50,
    actor_role: str | None = None,
    target_type: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch recent activity logs."""
    try:
        col = get_activity_logs_collection()
        if col is not None:
            query: dict[str, Any] = {}
            if actor_role:
                query["actor_role"] = actor_role
            if target_type:
                query["target_type"] = target_type

            cursor = col.find(query).sort("timestamp", -1).limit(limit)
            out = []
            for doc in cursor:
                doc["_id"] = str(doc.get("_id"))
                if isinstance(doc.get("created_at"), datetime):
                    doc["created_at"] = doc["created_at"].isoformat()
                out.append(doc)
            return out
    except Exception as exc:
        logger.warning("Error reading activity logs from MongoDB: %s", exc)

    # Fallback to in-memory logs
    logs = _in_memory_activity_fallback
    if actor_role:
        logs = [l for l in logs if l.get("actor_role") == actor_role]
    if target_type:
        logs = [l for l in logs if l.get("target_type") == target_type]
    return logs[:limit]


# ---------------------------------------------------------------- Student Documents
def save_student_resume_document(
    student_id: int,
    usn: str,
    resume_data: dict[str, Any],
) -> dict[str, Any]:
    """Save or update student resume / CV JSON document in MongoDB."""
    now = datetime.now(timezone.utc)
    doc = {
        "student_id": student_id,
        "usn": usn,
        "doc_type": "RESUME",
        "resume_data": resume_data,
        "updated_at": now.isoformat(),
    }

    try:
        col = get_student_documents_collection()
        if col is not None:
            col.update_one(
                {"student_id": student_id, "doc_type": "RESUME"},
                {"$set": doc},
                upsert=True,
            )
        else:
            _in_memory_docs_fallback[f"resume_{student_id}"] = doc
    except Exception as exc:
        logger.warning("Error saving resume in MongoDB: %s", exc)
        _in_memory_docs_fallback[f"resume_{student_id}"] = doc

    return doc


def get_student_resume_document(student_id: int) -> dict[str, Any] | None:
    """Get student resume document."""
    try:
        col = get_student_documents_collection()
        if col is not None:
            doc = col.find_one({"student_id": student_id, "doc_type": "RESUME"})
            if doc:
                doc["_id"] = str(doc.get("_id"))
                return doc
    except Exception as exc:
        logger.warning("Error fetching resume from MongoDB: %s", exc)

    return _in_memory_docs_fallback.get(f"resume_{student_id}")


def save_student_portfolio_item(
    student_id: int,
    usn: str,
    item_type: str,
    item_data: dict[str, Any],
) -> dict[str, Any]:
    """Store rich project documentation, case studies, or certificate artifacts."""
    now = datetime.now(timezone.utc)
    doc = {
        "student_id": student_id,
        "usn": usn,
        "doc_type": f"PORTFOLIO_{item_type.upper()}",
        "item_data": item_data,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }

    try:
        col = get_student_documents_collection()
        if col is not None:
            res = col.insert_one(doc)
            doc["_id"] = str(res.inserted_id)
        else:
            key = f"portfolio_{student_id}_{len(_in_memory_docs_fallback)}"
            _in_memory_docs_fallback[key] = doc
    except Exception as exc:
        logger.warning("Error saving portfolio item in MongoDB: %s", exc)
        key = f"portfolio_{student_id}_{len(_in_memory_docs_fallback)}"
        _in_memory_docs_fallback[key] = doc

    return doc


def get_student_portfolio_items(student_id: int) -> list[dict[str, Any]]:
    """Retrieve all rich portfolio documents for a student."""
    try:
        col = get_student_documents_collection()
        if col is not None:
            cursor = col.find({
                "student_id": student_id,
                "doc_type": {"$regex": "^PORTFOLIO_"}
            }).sort("created_at", -1)
            out = []
            for doc in cursor:
                doc["_id"] = str(doc.get("_id"))
                out.append(doc)
            return out
    except Exception as exc:
        logger.warning("Error reading portfolio from MongoDB: %s", exc)

    return [
        v for k, v in _in_memory_docs_fallback.items()
        if v.get("student_id") == student_id and v.get("doc_type", "").startswith("PORTFOLIO_")
    ]
