"""
Self-serve org signup with OTP verification
(.claude/plans/misty-growing-yao.md).

`captured_otp` fixture monkeypatches backend.routers.registration's
imported `send_otp_email` reference (not backend.email_util's, since
the router already bound the name at import time) to capture the code
instead of sending it — the universal way these tests "receive" an OTP.
"""

import pytest


@pytest.fixture()
def captured_otp(monkeypatch):
    captured = {}

    def fake_send(to_email, otp):
        captured["email"] = to_email
        captured["otp"] = otp

    monkeypatch.setattr("backend.routers.registration.send_otp_email", fake_send)
    return captured


def test_register_happy_path(client, captured_otp):
    r = client.post("/auth/register/request-otp", json={
        "org_name": "Acme Farms", "email": "New@Acme.com", "password": "supersecret1",
    })
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "new@acme.com"  # lowercased/stripped
    assert captured_otp["otp"]

    r2 = client.post("/auth/register/verify-otp", json={
        "email": "new@acme.com", "otp": captured_otp["otp"],
    })
    assert r2.status_code == 200, r2.text
    token = r2.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "new@acme.com"
    assert body["role"] == "admin"


def test_register_wrong_otp_increments_attempts(client, isolated_db, captured_otp):
    client.post("/auth/register/request-otp", json={
        "org_name": "Acme", "email": "wrong@acme.com", "password": "supersecret1",
    })

    r = client.post("/auth/register/verify-otp", json={"email": "wrong@acme.com", "otp": "000000"})
    assert r.status_code == 400

    row = isolated_db.get_pending_registration("wrong@acme.com")
    assert row["attempt_count"] == 1


def test_register_expired_otp(client, isolated_db, captured_otp):
    from sqlalchemy import text

    client.post("/auth/register/request-otp", json={
        "org_name": "Acme", "email": "expired@acme.com", "password": "supersecret1",
    })
    with isolated_db.get_db_connection() as conn:
        conn.execute(
            text("UPDATE pending_registrations SET expires_at = '2000-01-01T00:00:00+00:00' "
                 "WHERE email = :email"),
            {"email": "expired@acme.com"},
        )
        conn.commit()

    r = client.post("/auth/register/verify-otp", json={
        "email": "expired@acme.com", "otp": captured_otp["otp"],
    })
    assert r.status_code == 410


def test_register_max_attempts_lockout(client, captured_otp):
    client.post("/auth/register/request-otp", json={
        "org_name": "Acme", "email": "lockout@acme.com", "password": "supersecret1",
    })
    for _ in range(5):
        r = client.post("/auth/register/verify-otp", json={"email": "lockout@acme.com", "otp": "000000"})
        assert r.status_code == 400

    # Even the correct code is now locked out.
    r = client.post("/auth/register/verify-otp", json={
        "email": "lockout@acme.com", "otp": captured_otp["otp"],
    })
    assert r.status_code == 429


def test_register_resend_cooldown(client, captured_otp):
    r1 = client.post("/auth/register/request-otp", json={
        "org_name": "Acme", "email": "resend@acme.com", "password": "supersecret1",
    })
    assert r1.status_code == 200

    r2 = client.post("/auth/register/request-otp", json={
        "org_name": "Acme", "email": "resend@acme.com", "password": "supersecret1",
    })
    assert r2.status_code == 429


def test_register_duplicate_email_rejected(client, seeded_users, captured_otp):
    r = client.post("/auth/register/request-otp", json={
        "org_name": "Someone Else", "email": "admin@test.local", "password": "supersecret1",
    })
    assert r.status_code == 409


def test_register_short_password_rejected(client, captured_otp):
    r = client.post("/auth/register/request-otp", json={
        "org_name": "Acme", "email": "shortpw@acme.com", "password": "short",
    })
    assert r.status_code == 422


def test_register_concurrent_verify_race(client, isolated_db, captured_otp):
    client.post("/auth/register/request-otp", json={
        "org_name": "Acme", "email": "race@acme.com", "password": "supersecret1",
    })
    otp = captured_otp["otp"]

    r1 = client.post("/auth/register/verify-otp", json={"email": "race@acme.com", "otp": otp})
    r2 = client.post("/auth/register/verify-otp", json={"email": "race@acme.com", "otp": otp})

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 409]

    from sqlalchemy import text
    with isolated_db.get_db_connection() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM users WHERE email = :email"),
            {"email": "race@acme.com"},
        ).scalar()
    assert count == 1
