from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import OTPIn, StaffLoginIn, USNIn
from app.services import auth_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/student/request-otp")
def request_otp(body: USNIn, db: Session = Depends(get_db)):
    return auth_service.issue_student_challenge(db, body.usn)


@router.post("/student/verify-otp")
def verify_otp(body: OTPIn, db: Session = Depends(get_db)):
    user = auth_service.verify_student_otp(db, body.usn, body.otp)
    payload = auth_service.user_payload(db, user)
    return {"status": "ok", "token": user.active_session_token, "user": payload}


@router.post("/staff/login")
def staff_login(body: StaffLoginIn, db: Session = Depends(get_db)):
    user = auth_service.login_staff(db, body.email, body.password)
    payload = auth_service.user_payload(db, user)
    return {"status": "ok", "token": user.active_session_token, "user": payload}


@router.post("/logout")
def logout(db: Session = Depends(get_db), user=Depends(get_current_user)):
    auth_service.logout(db, user)
    return {"status": "ok"}


@router.get("/me")
def me(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return {"status": "ok", "user": auth_service.user_payload(db, user)}
