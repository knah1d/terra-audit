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
import socket
from email.message import EmailMessage

from backend.config import SMTP_CONFIGURED, SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

logger = logging.getLogger("terra_audit.registration")


class _IPv4SMTP(smtplib.SMTP):
    """smtplib.SMTP, but the connection socket is always resolved over
    IPv4. Some container platforms (Railway included) have no IPv6 egress
    route; smtp.gmail.com (and other providers) publish an AAAA record
    that Python's default getaddrinfo() ordering can try first, surfacing
    as OSError: [Errno 101] Network is unreachable before IPv4 is ever
    attempted. Overriding just _get_socket (not smtplib.SMTP.connect(),
    and not socket.getaddrinfo globally) keeps self._host as the real
    hostname, so starttls()'s server_hostname/certificate check below is
    unaffected — only which socket gets connected changes."""

    def _get_socket(self, host, port, timeout):
        addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        return socket.create_connection(addr_info[0][4], timeout, self.source_address)


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
        with _IPv4SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Failed to send OTP email to %s: %s", to_email, exc)
        raise EmailSendError("Could not send verification email") from exc
