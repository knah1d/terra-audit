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


def _ipv4_connect(host: str, port: int, timeout, source_address):
    """Some container platforms (Railway included) have no IPv6 egress
    route; smtp.gmail.com (and other providers) publish an AAAA record
    that Python's default getaddrinfo() ordering can try first, surfacing
    as OSError: [Errno 101] Network is unreachable before IPv4 is ever
    attempted. Shared by both _get_socket overrides below."""
    addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    return socket.create_connection(addr_info[0][4], timeout, source_address)


class _IPv4SMTP(smtplib.SMTP):
    """smtplib.SMTP (STARTTLS on an initially-plaintext connection, port
    587 by convention), but the connection socket is always IPv4 — see
    _ipv4_connect. Overriding just _get_socket (not smtplib.SMTP.connect(),
    and not socket.getaddrinfo globally) keeps self._host as the real
    hostname, so starttls()'s server_hostname/certificate check is
    unaffected — only which socket gets connected changes."""

    def _get_socket(self, host, port, timeout):
        return _ipv4_connect(host, port, timeout, self.source_address)


class _IPv4SMTP_SSL(smtplib.SMTP_SSL):
    """smtplib.SMTP_SSL (implicit TLS from the first byte, port 465 by
    convention) — some networks that block/drop STARTTLS's port 587 allow
    465, or vice versa, so SMTP_PORT picks which of these two classes is
    used (see send_otp_email below). Mirrors smtplib.SMTP_SSL's own
    _get_socket (base socket + wrap_socket) but over the IPv4-forced
    connection from _ipv4_connect instead of the default dual-stack one."""

    def _get_socket(self, host, port, timeout):
        sock = _ipv4_connect(host, port, timeout, self.source_address)
        return self.context.wrap_socket(sock, server_hostname=self._host)


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

    # 465 = implicit TLS from the first byte (no STARTTLS command); every
    # other port (587 by convention) = plaintext-then-upgrade. Some
    # networks' egress filtering treats these two differently, which is
    # exactly what SMTP_PORT=465 is for testing.
    try:
        if SMTP_PORT == 465:
            with _IPv4SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(message)
        else:
            with _IPv4SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("Failed to send OTP email to %s: %s", to_email, exc)
        raise EmailSendError("Could not send verification email") from exc
