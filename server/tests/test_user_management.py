from tests.conftest import auth, login
from tests.test_dqm_reports import users  # noqa: F401


def test_list_filters_and_stats(client, admin, users):  # noqa: F811
    all_users = client.get("/api/v1/admin/users", headers=admin).json()
    assert len(all_users) == 5  # admin + 4 fixture users
    assert sorted(u["username"] for u in client.get("/api/v1/admin/users", params={"role": "DISTRICT_DQM"}, headers=admin).json()) == ["dqm.war", "dqm.wau"]
    assert [u["username"] for u in client.get("/api/v1/admin/users", params={"search": "war"}, headers=admin).json()] == ["dqm.war"]
    assert [u["username"] for u in client.get("/api/v1/admin/users", params={"district_id": users["wau_id"]}, headers=admin).json()] == ["dqm.wau"]
    # A regional user counts as in scope for every district of the region
    names = {u["username"] for u in client.get("/api/v1/admin/users", params={"region_id": users["western"]}, headers=admin).json()}
    assert names == {"dqm.wau", "dqm.war", "regional"}
    s = client.get("/api/v1/admin/users/stats", headers=admin).json()
    assert s["total"] == 5 and s["active"] == 5 and s["by_role"]["DISTRICT_DQM"] == 2 and s["never_logged_in"] == 0


def test_reset_password_deactivate_activate(client, admin, users):  # noqa: F811
    uid = client.get("/api/v1/auth/me", headers=users["wau"]).json()["id"]
    r = client.post(f"/api/v1/admin/users/{uid}/reset-password", json={}, headers=admin)
    assert r.status_code == 200 and r.json()["temporary_password"]
    temp = r.json()["temporary_password"]
    assert client.post("/api/v1/auth/login", json={"username": "dqm.wau", "password": "Password123"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "dqm.wau", "password": temp}).status_code == 200
    # Explicit password
    assert client.post(f"/api/v1/admin/users/{uid}/reset-password", json={"password": "NewPass456"}, headers=admin).json()["temporary_password"] is None
    assert client.post("/api/v1/auth/login", json={"username": "dqm.wau", "password": "NewPass456"}).status_code == 200

    r = client.post(f"/api/v1/admin/users/{uid}/deactivate", headers=admin)
    assert r.status_code == 200 and r.json()["active"] is False
    assert client.post("/api/v1/auth/login", json={"username": "dqm.wau", "password": "NewPass456"}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=users["wau"]).status_code == 401  # existing token stops working
    assert client.post(f"/api/v1/admin/users/{uid}/activate", headers=admin).json()["active"] is True
    assert client.post("/api/v1/auth/login", json={"username": "dqm.wau", "password": "NewPass456"}).status_code == 200
    me = client.get("/api/v1/auth/me", headers=admin).json()
    assert client.post(f"/api/v1/admin/users/{me['id']}/deactivate", headers=admin).status_code == 400
    log = client.get("/api/v1/admin/audit", params={"entity": "user", "entity_id": uid, "action": "user."}, headers=admin).json()
    assert [x["action"] for x in log[:4]] == ["user.activate", "user.deactivate", "user.reset_password", "user.reset_password"]


def test_activity_view(client, admin, users):  # noqa: F811
    uid = client.get("/api/v1/auth/me", headers=users["wau"]).json()["id"]
    a = client.get(f"/api/v1/admin/users/{uid}/activity", headers=admin).json()
    assert a["user"]["username"] == "dqm.wau" and a["counts"]["logins"] == 1 and a["recent"][0]["action"] == "auth.login"
    assert a["devices"] == []


def test_bulk_import(client, admin, geo):
    csv = (
        "username,password,full_name,phone,role,districts,region\n"
        "dqm.import1,Password123,Import One,,DISTRICT_DQM,Western Area Urban,\n"
        "reg.import,Password123,Import Regional,,REGIONAL,,Western\n"
        "fm.import,,Import FM,+232,FIELD_MONITOR,WAU;WAR,\n"
        "bad.role,Password123,Bad Role,,MANAGER,,\n"
        "bad.district,Password123,Bad District,,DISTRICT_DQM,Nowhere,\n"
        "dqm.import1,Password123,Duplicate,,DISTRICT_DQM,WAU,\n"
    )
    r = client.post("/api/v1/admin/users/import", files={"file": ("users.csv", csv, "text/csv")}, headers=admin)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["created"] == 3 and res["skipped"] == 1 and len(res["errors"]) == 2
    fm = next(u for u in client.get("/api/v1/admin/users", headers=admin).json() if u["username"] == "fm.import")
    assert len(fm["scopes"]) == 2
    assert client.post("/api/v1/auth/login", json={"username": "dqm.import1", "password": "Password123"}).status_code == 200
    assert client.get("/api/v1/admin/users/template.csv", headers=admin).status_code == 200


def test_self_service_change_password(client, users):  # noqa: F811
    assert client.post("/api/v1/auth/change-password", json={"current_password": "wrong", "new_password": "Another123"}, headers=users["war"]).status_code == 400
    assert client.post("/api/v1/auth/change-password", json={"current_password": "Password123", "new_password": "Another123"}, headers=users["war"]).status_code == 204
    assert client.post("/api/v1/auth/login", json={"username": "dqm.war", "password": "Another123"}).status_code == 200
