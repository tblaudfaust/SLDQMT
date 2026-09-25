from tests.conftest import auth, login


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_login_and_me(client):
    data = login(client, "admin", "adminpass123")
    assert data["user"]["role"] == "ADMIN"
    assert data["settings"]["follow_up_interval_hours"] == "4"
    me = client.get("/api/v1/auth/me", headers=auth(data["access_token"])).json()
    assert me["username"] == "admin"


def test_bad_password_locks_after_attempts(client):
    for _ in range(5):
        r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "adminpass123"})
    assert r.status_code == 423


def test_refresh_rotates(client):
    data = login(client, "admin", "adminpass123")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert r.status_code == 200
    again = client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert again.status_code == 401


def test_import_creates_hierarchy(geo):
    res = geo["import"]
    assert res["regions"] == 1
    assert res["districts"] == 2
    assert res["teams"] == 2
    assert res["supervisors"] == 2
    assert res["enumerators"] == 3
    assert res["eas"] == 3
    assert res["warnings"] == []


def test_import_is_idempotent(client, admin, geo):
    csv = "Region,District Code,District,SA Code,SA Name,Supervisor\nWestern,WAU,Western Area Urban,WAU-SA01,Central One,Mohamed Kamara\n"
    r = client.post("/api/v1/admin/reference/import", files={"file": ("sa.csv", csv, "text/csv")}, headers=admin)
    assert r.json()["teams"] == 0
    teams = client.get("/api/v1/admin/reference/teams", headers=admin).json()
    assert [t for t in teams if t["code"] == "WAU-SA01"][0]["name"] == "Central One"


def test_field_monitor_cannot_use_admin(client, monitor):
    r = client.get("/api/v1/admin/users", headers=monitor["headers"])
    assert r.status_code == 403


def test_settings_update(client, admin):
    r = client.put("/api/v1/admin/settings", json={"follow_up_interval_hours": 6}, headers=admin)
    assert r.status_code == 200
    assert r.json()["follow_up_interval_hours"] == "6.0"
