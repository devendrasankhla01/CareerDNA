"""Authentication: USN→OTP institutional email login, staff email/password,
session management, rate limiting. Demo mode provides a fixed OTP fallback.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import timedelta

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.ratelimit import check_rate_limit
from app.db.session import get_db
from app.core.security import (
    generate_session_token,
    hash_otp,
    naive_utc,
    session_expiry,
    utcnow,
    verify_otp,
    verify_password,
    mask_email,
)
from app.models import (
    AuthChallenge,
    FacultyCategory,
    Session as UserSessionRow,
    Student,
    User,
)
from app.services import email_service

MAX_ATTEMPTS = 5
CHALLENGE_TTL_MIN = 10


def _get_user(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email.lower().strip())).scalars().first()


def _create_session(db: Session, user: User) -> None:
    row = UserSessionRow(
        token=generate_session_token(),
        user_id=user.id,
        created_at=utcnow(),
        expires_at=session_expiry(),
    )
    db.add(row)
    db.flush()
    user.active_session_token = row.token


def issue_student_challenge(db: Session, usn: str) -> dict:
    s = get_settings()
    usn = usn.strip().upper()
    if not usn:
        raise HTTPException(status_code=400, detail="USN is required")
    if not check_rate_limit(f"otp:{usn}", max(s.otp_max_attempts * 2, 8), s.otp_expiry_seconds):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    st = db.execute(select(Student).where(Student.usn == usn, Student.is_active == True)).scalars().first()  # noqa: E712
    if not st or not st.user:
        raise HTTPException(status_code=404, detail="USN not found or account inactive")
    if not st.user.is_active:
        raise HTTPException(status_code=403, detail="Account is locked")

    # supersede old pending challenges
    now = utcnow()
    for ch in db.execute(select(AuthChallenge).where(
        AuthChallenge.student_id == st.id, AuthChallenge.used_at.is_(None))).scalars():
        if naive_utc(ch.expires_at) > now:
            ch.expires_at = now  # mark expired

    otp = s.demo_otp if s.demo_mode else "".join(
        secrets.choice("0123456789") for _ in range(6))
    challenge = AuthChallenge(
        challenge_id=uuid.uuid4().hex,
        student_id=st.id,
        otp_hash=hash_otp(otp),
        max_attempts=MAX_ATTEMPTS,
        expires_at=now + timedelta(seconds=s.otp_expiry_seconds),
    )
    db.add(challenge)
    db.commit()

    delivered = True
    if not s.demo_mode and st.user.email:
        delivered = email_service.send_otp(st.user.email, usn, otp)
    return {
        "status": "ok",
        "usn": usn,
        "email_hint": mask_email(st.user.email) if st.user.email else None,
        "otp_sent": delivered,
        "demo_otp": s.demo_otp if s.demo_mode else None,
    }


def verify_student_otp(db: Session, usn: str, otp: str) -> User:
    usn = usn.strip().upper()
    st = db.execute(select(Student).where(Student.usn == usn, Student.is_active == True)).scalars().first()  # noqa: E712
    if not st or not st.user:
        raise HTTPException(status_code=404, detail="USN not found")

    now = utcnow()
    pending = db.execute(
        select(AuthChallenge)
        .where(AuthChallenge.student_id == st.id, AuthChallenge.used_at.is_(None))
        .order_by(AuthChallenge.created_at.desc())
    ).scalars().all()
    ch = next((c for c in pending if naive_utc(c.expires_at) > now), None)
    if ch is None:
        raise HTTPException(status_code=400, detail="No active verification request. Request a new code.")
    if ch.attempts >= ch.max_attempts:
        ch.used_at = now
        db.commit()
        raise HTTPException(status_code=429, detail="Too many incorrect attempts. Request a new code.")

    ch.attempts += 1
    if verify_otp(otp, ch.otp_hash):
        ch.used_at = now
        user = st.user
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is locked")
        user.last_login_at = now
        _create_session(db, user)
        db.commit()
        return user
    db.commit()
    remaining = ch.max_attempts - ch.attempts
    raise HTTPException(status_code=401, detail=f"Incorrect code. {remaining} attempts remaining.")


def login_staff(db: Session, email: str, password: str) -> User:
    if not check_rate_limit(f"login:{email.lower().strip()}", 5, 300):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    user = _get_user(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.role not in ("FACULTY", "VERIFIER", "DEPARTMENT", "COMPANY", "TPO_ADMIN"):
        raise HTTPException(status_code=403, detail="Staff login required")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is locked")
    user.last_login_at = utcnow()
    _create_session(db, user)
    db.commit()
    return user


def logout(db: Session, user: User) -> None:
    token = user.active_session_token
    if token:
        row = db.execute(select(UserSessionRow).where(UserSessionRow.token == token)).scalars().first()
        if row:
            db.delete(row)
            user.active_session_token = None
            db.commit()


def user_payload(db: Session, user: User) -> dict:
    out = {
        "id": user.id, "role": user.role, "email": user.email,
        "display_name": user.display_name, "is_active": user.is_active,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }
    if user.role == "STUDENT":
        st = db.execute(select(Student).where(Student.user_id == user.id)).scalars().first()
        if st:
            out["student"] = {
                "id": st.id, "usn": st.usn, "name": user.display_name,
                "branch": st.branch, "branch_display": st.branch,
                "semester": st.semester,
                "program": "B.Tech",
                "target_career_code": st.target_career_code,
                "profile_version": st.profile_version,
            }
    if user.role in ("FACULTY", "VERIFIER"):
        cats = db.execute(
            select(FacultyCategory).where(FacultyCategory.user_id == user.id)
        ).scalars().all()
        out["categories"] = [c.category for c in cats]
    if user.role == "DEPARTMENT" and user.department:
        out["department"] = {"code": user.department.code, "name": user.department.name}
    if user.role == "COMPANY" and user.company:
        out["company"] = {"id": user.company.id, "name": user.company.name}
    return out


def get_current_user(db: Session = Depends(get_db), authorization: str | None = Header(default=None)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    token = authorization.split(" ", 1)[1].strip()
    row = db.execute(select(UserSessionRow).where(UserSessionRow.token == token)).scalars().first()
    if not row or naive_utc(row.expires_at) < utcnow():
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Account is locked")
    # keep token in sync
    if user.active_session_token != token:
        user.active_session_token = token
    return user


def require_student(user: User = Depends(get_current_user)) -> User:
    if user.role != "STUDENT":
        raise HTTPException(status_code=403, detail="Student access required")
    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("FACULTY", "TPO_ADMIN"):
        raise HTTPException(status_code=403, detail="Staff access required")
    return user


def require_tpo(user: User = Depends(get_current_user)) -> User:
    if user.role != "TPO_ADMIN":
        raise HTTPException(status_code=403, detail="TPO access required")
    return user


def require_role(*roles: str):
    """Backend-enforced role gate. Usage: Depends(require_role("DEPARTMENT"))"""
    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Not authorized for this resource")
        return user
    return _check


def require_department(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("DEPARTMENT", "TPO_ADMIN"):
        raise HTTPException(status_code=403, detail="Department access required")
    if user.role == "DEPARTMENT" and not user.department:
        raise HTTPException(status_code=403, detail="Department account not linked")
    return user


def require_company(user: User = Depends(get_current_user)) -> User:
    if user.role != "COMPANY":
        raise HTTPException(status_code=403, detail="Company access required")
    if not user.company_id:
        raise HTTPException(status_code=403, detail="Company account not linked")
    return user


def require_verifier(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("FACULTY", "VERIFIER"):
        raise HTTPException(status_code=403, detail="Verifier access required")
    return user


def get_student_for_user(db: Session, user: User) -> Student:
    st = db.execute(select(Student).where(Student.user_id == user.id)).scalars().first()
    if not st:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return st
