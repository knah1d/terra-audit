"""Single-use, hashed account invitations and recovery tokens."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from src.auth import hash_password
from src.database import get_db_connection


def initialize_tables(conn):
    conn.execute(text("""CREATE TABLE IF NOT EXISTS account_links (
        token_hash TEXT PRIMARY KEY, org_id TEXT NOT NULL, email TEXT NOT NULL,
        purpose TEXT NOT NULL, role TEXT NOT NULL, created_by TEXT,
        created_at TEXT NOT NULL, expires_at TEXT NOT NULL, consumed_at TEXT)"""))
    conn.execute(text("""CREATE TABLE IF NOT EXISTS account_token_versions (
        user_id TEXT PRIMARY KEY, version INTEGER NOT NULL DEFAULT 0)"""))
    conn.execute(text("""CREATE TABLE IF NOT EXISTS account_rate_limits (
        rate_key TEXT PRIMARY KEY, window_start TEXT NOT NULL, count INTEGER NOT NULL)"""))


def token_version(user_id):
    with get_db_connection() as conn:
        return conn.execute(text("SELECT version FROM account_token_versions WHERE user_id=:u"), {"u": user_id}).scalar() or 0


def throttle(key, limit, seconds):
    now = datetime.now(timezone.utc)
    window = str(int(now.timestamp()) // seconds)
    hashed = hashlib.sha256(key.encode()).hexdigest()
    with get_db_connection() as conn:
        conn.execute(text("""INSERT INTO account_rate_limits(rate_key,window_start,count) VALUES (:k,:w,0)
            ON CONFLICT(rate_key) DO NOTHING"""), {"k": hashed, "w": window})
        conn.execute(text("UPDATE account_rate_limits SET window_start=:w,count=0 WHERE rate_key=:k AND window_start<>:w"),
                     {"k": hashed, "w": window})
        ok = conn.execute(text("UPDATE account_rate_limits SET count=count+1 WHERE rate_key=:k AND window_start=:w AND count<:n"),
                          {"k": hashed, "w": window, "n": limit}).rowcount
        conn.commit()
    return bool(ok)


def create_link(org_id, email, purpose, role, actor=None):
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with get_db_connection() as conn:
        # Issuing a replacement invalidates older links for this address/purpose.
        conn.execute(text("UPDATE account_links SET consumed_at=:now WHERE org_id=:o AND email=:e AND purpose=:p AND consumed_at IS NULL"),
                     {"now": now.isoformat(), "o": org_id, "e": email, "p": purpose})
        conn.execute(text("""INSERT INTO account_links(token_hash,org_id,email,purpose,role,created_by,created_at,expires_at)
            VALUES (:h,:o,:e,:p,:r,:a,:now,:expires)"""), {
            "h": hashlib.sha256(token.encode()).hexdigest(), "o": org_id, "e": email, "p": purpose, "r": role,
            "a": actor, "now": now.isoformat(), "expires": (now + timedelta(hours=48 if purpose == "invite" else 1)).isoformat()})
        conn.commit()
    return token


def consume_link(token, password):
    if not 12 <= len(password) or len(password.encode()) > 72:
        raise ValueError("Password must contain at least 12 characters and at most 72 UTF-8 bytes")
    now = datetime.now(timezone.utc).isoformat()
    hashed = hashlib.sha256(token.encode()).hexdigest()
    password_hash = hash_password(password)
    with get_db_connection() as conn:
        row = conn.execute(text("SELECT * FROM account_links WHERE token_hash=:h AND consumed_at IS NULL AND expires_at>:now"),
                           {"h": hashed, "now": now}).mappings().first()
        if not row:
            raise ValueError("Link is invalid, expired, or already used")
        if row["purpose"] == "invite":
            creator = conn.execute(text("SELECT 1 FROM users WHERE user_id=:u AND org_id=:o AND role='admin' AND is_active=1"),
                                   {"u": row["created_by"], "o": row["org_id"]}).first()
            if not creator:
                raise ValueError("Invitation is no longer authorized; ask your administrator for a new one")
        claimed = conn.execute(text("UPDATE account_links SET consumed_at=:now WHERE token_hash=:h AND consumed_at IS NULL AND expires_at>:now"),
                               {"h": hashed, "now": now}).rowcount
        if claimed != 1:
            raise ValueError("Link has already been used")
        user = conn.execute(text("SELECT user_id,is_active,org_id FROM users WHERE email=:e"), {"e": row["email"]}).mappings().first()
        if row["purpose"] == "invite":
            if user:
                raise ValueError("This email already has an account; use password recovery")
            uid = uuid.uuid4().hex
            conn.execute(text("INSERT INTO users(user_id,org_id,email,password_hash,role) VALUES (:u,:o,:e,:p,:r)"),
                         {"u": uid, "o": row["org_id"], "e": row["email"], "p": password_hash, "r": row["role"]})
        else:
            if not user or not user["is_active"] or user["org_id"] != row["org_id"]:
                raise ValueError("This recovery link is no longer valid")
            uid = user["user_id"]
            conn.execute(text("UPDATE users SET password_hash=:p WHERE user_id=:u"), {"p": password_hash, "u": uid})
        conn.execute(text("""INSERT INTO account_token_versions(user_id,version) VALUES (:u,1)
            ON CONFLICT(user_id) DO UPDATE SET version=account_token_versions.version+1"""), {"u": uid})
        conn.commit()
