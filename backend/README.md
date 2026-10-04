# Terra Audit API

FastAPI backend wrapping the existing `src/` calculation/pipeline logic
behind REST endpoints for the Next.js frontend. The durable worker uses
the same core and database; the legacy Streamlit UI has been retired.

## Run

```bash
source venv/bin/activate
uvicorn backend.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs

Set `JWT_SECRET` in `.env` before running this anywhere but a local
laptop. Render (or `APP_ENV=production`) rejects missing or short secrets
and requires an HTTPS `FRONTEND_PUBLIC_URL` with a non-local host. Local
development retains a warned signing-key fallback.

### Self-serve signup (OTP email)

`POST /auth/register/request-otp` + `POST /auth/register/verify-otp`
(see `.claude/plans/misty-growing-yao.md`) let anyone create a brand-new
org + become its first admin, verified via a 6-digit email code. Sent via
Brevo's HTTPS API, not SMTP — confirmed by direct testing that Railway
silently drops outbound traffic on SMTP ports 587 and 465 (the connection
hangs until timeout rather than being refused), a common anti-abuse
egress policy on PaaS hosts; HTTPS doesn't have this problem. (SendGrid
was tried first — its new-account fraud review locked the account out
before it could be used at all; Brevo's signup didn't have that problem.)
Add to `.env` to send real email:

```
BREVO_API_KEY=
EMAIL_FROM=no-reply@yourdomain.com  # must match a sender verified in Brevo
OTP_EXPIRE_MINUTES=10
OTP_MAX_ATTEMPTS=5
OTP_RESEND_COOLDOWN_SECONDS=60
```

`EMAIL_FROM` verification is single-sender (verify one specific address
via a confirmation email — no domain purchase required).

Without `BREVO_API_KEY` set, a `UserWarning` fires at startup and the
OTP is instead logged to stdout prefixed `[DEV-ONLY OTP]` — fine for
local dev, not for any real deployment.

## Tests

```bash
pytest tests/backend/ -v
```

Each test runs against an isolated throwaway SQLite file (never the real
`data/project_store.db`) and stubs out `SpatialDataEngine` so no test
requires real Earth Engine credentials — see `tests/backend/conftest.py`.

## Notes

- Every router calls `src.*` directly — nothing under `backend/` forks or
  duplicates calculation/persistence logic.
- `org_id` always comes from the JWT, never from a URL path or request
  body.
- Signal-analytics (GEE fetch) and AI training run as background jobs
  (`background_jobs` table in `src/persistence/database.py`) when the DB cache
  misses; a cache hit stays synchronous. See plan Part A4.
