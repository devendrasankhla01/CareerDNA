"""Central application configuration.

All business thresholds and tunables live here (or in the seeded
configuration tables) so that no numeric rule is duplicated across the app.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]  # backend/
load_dotenv(BASE_DIR / ".env")
load_dotenv()  # also load from current working directory if different


def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def settings():
    return _Settings()


class _Settings:
    """Environment-driven settings with safe local defaults for the demo."""

    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "CareerDNA")
        self.institution_name = os.getenv(
            "INSTITUTION_NAME", "Northfield Institute of Technology"
        )
        # Domain used to derive a student's institutional email when the
        # import CSV does not provide one: {usn.lower()}@<domain>.
        self.institution_email_domain = os.getenv(
            "INSTITUTION_EMAIL_DOMAIN", "northfielddemo.edu"
        )
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # When running on Vercel serverless, copy SQLite DB and evidence storage to /tmp
        if os.getenv("VERCEL"):
            import shutil
            tmp_db = Path("/tmp/careerdna.db")
            src_db = BASE_DIR / "careerdna.db"
            if not tmp_db.exists() and src_db.exists():
                try:
                    shutil.copyfile(src_db, tmp_db)
                except Exception:
                    pass
            self.database_url = os.getenv("DATABASE_URL", f"sqlite:///{tmp_db}")
            self.storage_dir = Path(os.getenv("STORAGE_DIR", "/tmp/storage/evidence"))
        else:
            self.database_url = os.getenv(
                "DATABASE_URL", f"sqlite:///{BASE_DIR}/careerdna.db"
            )
            self.storage_dir = Path(os.getenv("STORAGE_DIR", str(BASE_DIR / "storage" / "evidence")))

        self.secret_key = os.getenv("SECRET_KEY", "dev-only-secret-change-me")
        self.frontend_origin = os.getenv("FRONTEND_ORIGIN", "*")

        # MongoDB settings (optional document store & activity logs)
        self.mongodb_url = os.getenv("MONGODB_URL", "")
        self.mongodb_db_name = os.getenv("MONGODB_DB_NAME", "careerdna")

        # Demo mode: allows fixed demo OTP when SMTP is not configured.
        # Never enable in a real institutional deployment.
        self.demo_mode = _env_bool("DEMO_MODE", "true")
        self.demo_otp = os.getenv("DEMO_OTP", "246810")

        # SMTP (optional). When unset and demo_mode is on, the demo OTP is used.
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_sender = os.getenv("SMTP_SENDER", "careerdna@northfielddemo.edu")
        self.smtp_tls = _env_bool("SMTP_TLS", "true")

        self.model_dir = Path(os.getenv("MODEL_DIR", str(BASE_DIR / "artifacts")))
        self.max_upload_mb = float(os.getenv("MAX_UPLOAD_MB", "5"))

        # Readiness bands (percent). Needs Training < 60, Near-Ready < 80, Ready >= 80.
        self.needs_training_lt = float(os.getenv("THRESHOLD_NEEDS_TRAINING_LT", "60"))
        self.near_ready_lt = float(os.getenv("THRESHOLD_NEAR_READY_LT", "80"))
        self.ready_target = float(os.getenv("TARGET_READY", "80"))
        self.career_target_match = float(os.getenv("TARGET_CAREER_MATCH", "80"))
        self.vulnerable_lt = float(os.getenv("THRESHOLD_VULNERABLE_LT", "60"))

        # OTP policy
        self.otp_expiry_seconds = int(os.getenv("OTP_EXPIRY_SECONDS", "300"))
        self.otp_resend_cooldown = int(os.getenv("OTP_RESEND_COOLDOWN", "45"))
        self.otp_max_attempts = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
        self.session_max_age_hours = int(os.getenv("SESSION_MAX_AGE_HOURS", "12"))

        # Trust / verification-coverage weights (prototype configuration)
        self.trust_weights = {
            "ACADEMIC": 25,
            "TECHNICAL": 25,
            "PRACTICAL": 20,
            "ASSESSMENT": 15,
            "COMMUNICATION": 10,
            "ACTIVITY": 5,
        }

        # Intervention engine
        self.intervention_min_population = int(os.getenv("INTERVENTION_MIN_POPULATION", "15"))
        self.intervention_default_improvement = float(os.getenv("INTERVENTION_DEFAULT_IMPROVEMENT", "15"))

        # ---------------------------------------------------------------- placement
        # Placement Match Engine — transparent, configurable component weights.
        # These are prototype weights (sum to 1.0); documented, never random.
        # Company Match is computed ONLY after mandatory eligibility is evaluated;
        # a failed mandatory criterion can never be "averaged away" into the score.
        self.company_match_weights = {
            "required_skills": 0.30,     # alignment with the drive's required skill list
            "preferred_skills": 0.15,    # alignment with the drive's preferred skill list
            "career": 0.20,              # career-track match (existing career engine)
            "readiness": 0.15,           # ML placement-readiness score (one input, not the whole rule)
            "coding_aptitude": 0.10,     # coding/aptitude vs drive thresholds
            "project_internship": 0.10,  # relevant project/internship exposure
        }
        # Company match is shown to students only for OPEN drives.
        self.allow_student_interest = _env_bool("ALLOW_STUDENT_INTEREST", "true")
        # Verification escalation: requests pending longer than this are flagged.
        self.verification_escalation_days = int(os.getenv("VERIFICATION_ESCALATION_DAYS", "3"))
        # Students must have this much verified coverage for company match to be
        # computed at all (prevents match on an empty/low-trust profile).
        self.min_coverage_for_match = float(os.getenv("MIN_COVERAGE_FOR_MATCH", "0"))

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


def get_settings() -> _Settings:
    return settings()
