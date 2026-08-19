"""
OTP email delivery for self-serve org signup
(.claude/plans/misty-growing-yao.md).

Uses stdlib smtplib/email — deliberately no new pip dependency for what
is, at this app's scale, a single templated message. Falls back to
logging the code when SMTP_* isn't configured (backend/config.py's
SMTP_CONFIGURED), so local dev never requires a real mail server.
"""

import logging
import smtplib
from email.message import EmailMessage

from backend.config import SMTP_CONFIGURED, SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

logger = logging.getLogger("terra_audit.registration")


class EmailSendError(RuntimeError):
    """Raised when SMTP delivery fails — the router turns this into a 502
    rather than letting a bare smtplib traceback reach the client."""


def send_otp_email(to_email: str, otp: str) -> None:
    if not SMTP_CONFIGURED:
        # The ONLY place the raw OTP is ever surfaced, and only reached
        # when SMTP isn't configured — never in a real deployment that
        # set SMTP_HOST/SMTP_USER/SMTP_PASSWORD correctly. print(), not
        # logger.info(): this codebase has no logging.basicConfig() call
        # anywhere, so an INFO-level record would silently vanish (the
        # root logger's default level is WARNING with no handler attached)
        # — defeating the entire point of a *visible* dev fallback. The
        # prefix makes a stray occurrence of this line in real output
        # easy to grep for.
        print(f"[DEV-ONLY OTP] {to_email}: {otp}")
        return

    message = EmailMessage()
    message["Subject"] = "Your Terra Audit verification code"
    message["From"] = SMTP_FROM
    message["To"] = to_email
    message.set_content(
        f"Your Terra Audit verification code is: {otp}\n\n"
        "This code expires shortly and can only be used once. If you didn't "
        "request this, you can safely ignore this email."
    )

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Failed to send OTP email to %s: %s", to_email, exc)
        raise EmailSendError("Could not send verification email") from exc
