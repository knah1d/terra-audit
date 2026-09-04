"""
OTP email delivery for self-serve org signup
(.claude/plans/misty-growing-yao.md).

Sent via Resend's HTTPS API (urllib.request, stdlib only — deliberately
no new pip dependency for what is, at this app's scale, a single
templated message), not SMTP. Confirmed by direct testing that Railway
silently drops outbound traffic on both SMTP ports 587 and 465 — the
connection hangs until timeout rather than being refused, a common
anti-abuse egress policy on PaaS hosts. HTTPS (443) doesn't have this
problem. Falls back to logging the code when RESEND_API_KEY isn't set
(backend/config.py's EMAIL_CONFIGURED), so local dev never requires a
real Resend account.
"""

import json
import logging
import urllib.error
import urllib.request

from backend.config import EMAIL_CONFIGURED, EMAIL_FROM, RESEND_API_KEY

logger = logging.getLogger("terra_audit.registration")

RESEND_API_URL = "https://api.resend.com/emails"


class EmailSendError(RuntimeError):
    """Raised when email delivery fails — the router turns this into a 502
    rather than letting a bare urllib traceback reach the client."""


def send_otp_email(to_email: str, otp: str) -> None:
    if not EMAIL_CONFIGURED:
        # The ONLY place the raw OTP is ever surfaced, and only reached
        # when Resend isn't configured — never in a real deployment that
        # set RESEND_API_KEY correctly. print(), not logger.info(): this
        # codebase has no logging.basicConfig() call anywhere, so an
        # INFO-level record would silently vanish (the root logger's
        # default level is WARNING with no handler attached) — defeating
        # the entire point of a *visible* dev fallback. The prefix makes a
        # stray occurrence of this line in real output easy to grep for.
        print(f"[DEV-ONLY OTP] {to_email}: {otp}")
        return

    body = json.dumps({
        "from": EMAIL_FROM,
        "to": [to_email],
        "subject": "Your Terra Audit verification code",
        "text": (
            f"Your Terra Audit verification code is: {otp}\n\n"
            "This code expires shortly and can only be used once. If you didn't "
            "request this, you can safely ignore this email."
        ),
    }).encode("utf-8")

    request = urllib.request.Request(
        RESEND_API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            # Without a real User-Agent, urllib's default
            # ("Python-urllib/3.x") gets blocked by Cloudflare's bot
            # protection in front of api.resend.com (error code 1010) —
            # confirmed by direct testing, before any API-key check is
            # even reached.
            "User-Agent": "terra-audit-backend/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10):
            pass
    except (urllib.error.URLError, OSError) as exc:
        # urllib.error.HTTPError (a 4xx/5xx from Resend, e.g. unverified
        # sender domain) is also a URLError — its .read() body carries
        # Resend's actual error message, more useful than str(exc) alone.
        detail = exc.read().decode("utf-8", errors="replace") if isinstance(exc, urllib.error.HTTPError) else str(exc)
        logger.error("Failed to send OTP email to %s: %s", to_email, detail)
        raise EmailSendError("Could not send verification email") from exc
