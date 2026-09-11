"""Email adapter for OTP delivery.

Demo mode: no SMTP needed — the fixed demo OTP is returned to the client
and also written to the server log (clearly labelled).
Production: configure SMTP_HOST etc. via environment variables and the
same interface works with any free SMTP relay (e.g. the institution's mail
relay). Zero-cost by design.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("careerdna.email")


def send_otp(to_email: str, usn: str, otp: str) -> bool:
    host = os.environ.get("SMTP_HOST", "")
    if not host:
        # Local demo path: log only (no network, no cost).
        logger.info("[EMAIL-DEMO] To=%s USN=%s OTP=%s (SMTP not configured; demo fallback active)",
                    to_email, usn, otp)
        return True

    # Real SMTP path (optional, only if configured).
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(
        f"Your CareerDNA verification code is {otp}. It expires in 10 minutes. "
        "If you did not request this, you can ignore this email."
    )
    msg["Subject"] = "CareerDNA verification code"
    msg["From"] = os.environ.get("SMTP_FROM", "careerdna@northfielddemo.edu")
    msg["To"] = to_email
    try:
        with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as s:
            s.starttls()
            if os.environ.get("SMTP_USER"):
                s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
            s.send_message(msg)
        return True
    except Exception as e:  # pragma: no cover
        logger.error("SMTP send failed: %s", e)
        return False
