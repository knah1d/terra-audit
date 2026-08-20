"""
Regression tests for the team-management router (backend/routers/team.py) —
the one true backend gap the Streamlit-vs-frontend feature audit found:
create_org_user/list_org_users existed only as functions app.py called
directly, never exposed over the API.
"""


def test_non_admin_cannot_list_team(client, auth_headers):
    r = client.get("/team/users", headers=auth_headers["analyst"])
    assert r.status_code == 403


def test_non_admin_cannot_invite(client, auth_headers):
    r = client.post("/team/users", json={
        "email": "new@test.local", "password": "NewPass123!", "role": "viewer",
    }, headers=auth_headers["viewer"])
    assert r.status_code == 403


def test_admin_can_list_team(client, auth_headers):
    r = client.get("/team/users", headers=auth_headers["admin"])
    assert r.status_code == 200
    emails = {row["email"] for row in r.json()}
    assert "admin@test.local" in emails
    assert "analyst@test.local" in emails


def test_admin_can_invite_teammate(client, auth_headers):
    r = client.post("/team/users", json={
        "email": "invited@test.local", "password": "InvitedPass123!", "role": "analyst",
    }, headers=auth_headers["admin"])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == "invited@test.local"
    assert body["role"] == "analyst"

    listing = client.get("/team/users", headers=auth_headers["admin"]).json()
    assert any(row["email"] == "invited@test.local" for row in listing)


def test_duplicate_email_is_409_not_500(client, auth_headers):
    r = client.post("/team/users", json={
        "email": "admin@test.local", "password": "WhoCares123!", "role": "viewer",
    }, headers=auth_headers["admin"])
    assert r.status_code == 409


def test_invalid_role_is_422(client, auth_headers):
    r = client.post("/team/users", json={
        "email": "badrole@test.local", "password": "WhoCares123!", "role": "superuser",
    }, headers=auth_headers["admin"])
    assert r.status_code == 422


def test_team_roster_is_org_scoped(client, auth_headers):
    """An org's admin must never see another org's users."""
    r = client.get("/team/users", headers=auth_headers["other_org_admin"])
    assert r.status_code == 200
    emails = {row["email"] for row in r.json()}
    assert "admin@test.local" not in emails
    assert "otheradmin@test.local" in emails
