def test_login_success_and_me(client, seeded_users):
    r = client.post("/auth/login", json={"email": "admin@test.local", "password": "AdminPass123!"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["org_id"] == "testorg"
    assert body["role"] == "admin"
    assert body["email"] == "admin@test.local"


def test_login_wrong_password(client, seeded_users):
    r = client.post("/auth/login", json={"email": "admin@test.local", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_email(client, seeded_users):
    r = client.post("/auth/login", json={"email": "nobody@test.local", "password": "x"})
    assert r.status_code == 401


def test_me_without_token_is_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401
