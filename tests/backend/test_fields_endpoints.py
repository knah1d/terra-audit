from tests.backend.conftest import RICE_FEATURE


def test_create_get_list_field(client, auth_headers):
    r = client.post("/fields", json={
        "field_id": "F-1", "name": "Field One", "district": "D1",
        "field_type": "rice_awd", "feature": RICE_FEATURE,
    }, headers=auth_headers["admin"])
    assert r.status_code == 201
    body = r.json()
    assert body["field_type"] == "rice_awd"
    assert body["area_ha"] > 0

    r = client.get("/fields/F-1", headers=auth_headers["admin"])
    assert r.status_code == 200
    assert r.json()["geojson_geometry"]["type"] == "FeatureCollection"

    r = client.get("/fields", headers=auth_headers["admin"])
    assert [f["field_id"] for f in r.json()] == ["F-1"]


def test_duplicate_field_id_409(client, rice_field, auth_headers):
    r = client.post("/fields", json={
        "field_id": rice_field, "name": "dup", "district": "dup",
        "field_type": "rice_awd", "feature": RICE_FEATURE,
    }, headers=auth_headers["admin"])
    assert r.status_code == 409


def test_viewer_cannot_create_field(client, auth_headers):
    r = client.post("/fields", json={
        "field_id": "F-VIEWER", "name": "x", "district": "x",
        "field_type": "rice_awd", "feature": RICE_FEATURE,
    }, headers=auth_headers["viewer"])
    assert r.status_code == 403


def test_analyst_can_edit_but_not_delete(client, rice_field, auth_headers):
    r = client.patch(f"/fields/{rice_field}", json={"name": "Renamed", "district": "D2"},
                      headers=auth_headers["analyst"])
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"

    r = client.delete(f"/fields/{rice_field}", headers=auth_headers["analyst"])
    assert r.status_code == 403  # delete is admin-only, stricter than edit


def test_admin_can_delete_field(client, rice_field, auth_headers):
    r = client.delete(f"/fields/{rice_field}", headers=auth_headers["admin"])
    assert r.status_code == 204
    r = client.get(f"/fields/{rice_field}", headers=auth_headers["admin"])
    assert r.status_code == 404


def test_cross_org_isolation(client, rice_field, auth_headers):
    """A field created under 'testorg' must be invisible to 'otherorg'."""
    r = client.get("/fields", headers=auth_headers["other_org_admin"])
    assert r.json() == []
    r = client.get(f"/fields/{rice_field}", headers=auth_headers["other_org_admin"])
    assert r.status_code == 404


def test_parse_coordinates_and_area(client, auth_headers):
    r = client.post("/fields/parse/coordinates", json={
        "text": "23.0, 90.0\n23.0, 90.01\n23.01, 90.01\n23.01, 90.0",
    }, headers=auth_headers["admin"])
    assert r.status_code == 200
    feature = r.json()["feature"]
    assert feature["geometry"]["type"] == "Polygon"

    r = client.post("/geometry/area", json=feature, headers=auth_headers["admin"])
    assert r.status_code == 200
    assert r.json()["area_ha"] > 0


def test_parse_coordinates_error_surfaces_as_error_field(client, auth_headers):
    r = client.post("/fields/parse/coordinates", json={"text": "not coordinates"},
                     headers=auth_headers["admin"])
    assert r.status_code == 200  # parse failure is a normal 200 with `error` set, not a 4xx
    body = r.json()
    assert body["feature"] is None
    assert body["error"] is not None
