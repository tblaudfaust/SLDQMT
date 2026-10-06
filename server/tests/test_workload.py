"""Workload assignment: SAs carry Field Monitor / DQM codes, accounts link by staff code,
tablets receive only their own SAs and a DQM's dashboard defaults to their own SAs."""

import uuid

from tests.conftest import auth, login, make_error

WORKLOAD_CSV = (
    "Region,District,SA code,SA name,Field monitor ID,DQM ID\n"
    "Western,Western Area Urban,WAU-SA01,Central 1,FM-WAU-001,DQM-WAU-001\n"
    "Western,Western Area Urban,WAU-SA02,Central 2,FM-WAU-002,DQM-WAU-002\n"
    "Western,Western Area Rural,WAR-SA01,Waterloo 1,FM-WAR-001,DQM-WAR-001\n"
)


def _import_workload(client, admin):
    r = client.post("/api/v1/admin/reference/import", files={"file": ("workload.csv", WORKLOAD_CSV, "text/csv")}, headers=admin)
    assert r.status_code == 200, r.text
    return r.json()


def test_workload_import_assigns_sas(client, admin, geo):
    result = _import_workload(client, admin)
    assert result["assigned"] == 3
    assert result["teams"] == 1  # WAU-SA02 is new; the other two already existed
    teams = {t["code"]: t for t in client.get("/api/v1/admin/reference/teams", headers=admin).json()}
    assert teams["WAU-SA01"]["monitor_code"] == "FM-WAU-001" and teams["WAU-SA01"]["dqm_code"] == "DQM-WAU-001"
    assert teams["WAR-SA01"]["monitor_code"] == "FM-WAR-001"
    # re-import is idempotent
    assert _import_workload(client, admin)["teams"] == 0
    rows = client.get("/api/v1/admin/reference/workload?search=FM-WAU", headers=admin).json()
    assert {r["code"] for r in rows} == {"WAU-SA01", "WAU-SA02"}
    assert rows[0]["monitor_name"] is None  # no account yet


def test_field_monitor_bundle_is_limited_to_own_sas(client, admin, geo):
    _import_workload(client, admin)
    wau = geo["districts"]["WAU"]["id"]
    body = {"username": "fm-wau-001", "password": "Password123", "full_name": "Field Monitor FM-WAU-001", "role": "FIELD_MONITOR", "district_ids": [wau], "staff_code": "fm-wau-001"}
    r = client.post("/api/v1/admin/users", json=body, headers=admin)
    assert r.status_code == 201, r.text
    assert r.json()["staff_code"] == "FM-WAU-001"  # typed in lower case, stored canonically
    device = str(uuid.uuid4())
    data = login(client, "fm-wau-001", "Password123", device)
    assert data["user"]["assigned_sas"] == 1 and data["user"]["staff_code"] == "FM-WAU-001"
    headers = auth(data["access_token"])
    assert client.post("/api/v1/devices/register", json={"device_id": device, "model": "Test tablet", "android_version": "13", "app_version": "0.3.0"}, headers=headers).status_code == 200
    pr = client.get(f"/api/v1/sync/pull?device_id={device}", headers=headers)
    assert pr.status_code == 200, pr.text
    pull = pr.json()
    codes = {t["code"] for t in pull["reference"]["teams"]}
    assert codes == {"WAU-SA01"}  # not WAU-SA02, which belongs to FM-WAU-002
    assert {e["code"] for e in pull["reference"]["eas"]} == {"WAU-SA01-EA01", "WAU-SA01-EA02"}
    version = pull["reference_version"]

    # the workload page shows the account against the SA
    rows = client.get("/api/v1/admin/reference/workload?search=WAU-SA01", headers=admin).json()
    assert rows[0]["monitor_name"] == "Field Monitor FM-WAU-001"

    # reassigning the SA changes the bundle version so the tablet refreshes
    r = client.post("/api/v1/admin/reference/import", files={"file": ("w.csv", "District,SA code,Field monitor ID,DQM ID\nWestern Area Urban,WAU-SA02,FM-WAU-001,DQM-WAU-001\n", "text/csv")}, headers=admin)
    assert r.status_code == 200, r.text
    pull2 = client.get(f"/api/v1/sync/pull?device_id={device}&reference_version={version}", headers=headers).json()
    assert pull2["reference"] is not None and {t["code"] for t in pull2["reference"]["teams"]} == {"WAU-SA01", "WAU-SA02"}


def test_dqm_dashboard_defaults_to_own_sas(client, admin, geo, monitor):
    _import_workload(client, admin)
    wau = geo["districts"]["WAU"]["id"]
    teams = {t["code"]: t for t in client.get("/api/v1/admin/reference/teams", headers=admin).json()}
    # one error on WAU-SA01 (DQM-WAU-001's SA) and one on WAU-SA02 (DQM-WAU-002's SA)
    for code in ("WAU-SA01", "WAU-SA02"):
        err = make_error(geo, team_id=teams[code]["id"], description=f"error on {code}")
        r = client.post("/api/v1/sync/push", json={"device_id": monitor["device_id"], "errors": [err]}, headers=monitor["headers"])
        assert r.status_code == 200, r.text
        assert all(x["result"] != "rejected" for x in r.json()["receipts"]), r.text
    r = client.post("/api/v1/admin/users", json={"username": "dqm-wau-001", "password": "Password123", "full_name": "DQM 51-001", "role": "DISTRICT_DQM", "district_ids": [wau], "staff_code": "DQM-WAU-001"}, headers=admin)
    assert r.status_code == 201, r.text
    dqm = auth(login(client, "dqm-wau-001", "Password123")["access_token"])
    own = client.get("/api/v1/errors", headers=dqm).json()
    assert own["total"] == 1 and own["items"][0]["team"].startswith("WAU-SA01")
    whole = client.get("/api/v1/errors?own_sas=false", headers=dqm).json()
    assert whole["total"] == 2


def test_reassign_sas_within_district(client, admin, geo):
    """SAs can be moved to another officer of the same district; other districts are refused; tablets refresh."""
    _import_workload(client, admin)
    wau = geo["districts"]["WAU"]["id"]
    teams = {t["code"]: t for t in client.get("/api/v1/admin/reference/teams", headers=admin).json()}
    for code, role in (("FM-WAU-001", "FIELD_MONITOR"), ("FM-WAU-002", "FIELD_MONITOR"), ("DQM-WAU-002", "DISTRICT_DQM")):
        r = client.post("/api/v1/admin/users", json={"username": code.lower(), "password": "Password123", "full_name": f"Western Urban {code.split('-')[0]} {code[-3:]}", "role": role, "district_ids": [wau], "staff_code": code}, headers=admin)
        assert r.status_code == 201, r.text
    offs = client.get(f"/api/v1/admin/reference/officers?district_id={wau}", headers=admin).json()
    by = {o["staff_code"]: o for o in offs}
    assert by["FM-WAU-001"]["sa_count"] == 1 and by["FM-WAU-001"]["full_name"] == "Western Urban FM 001"
    assert by["DQM-WAU-001"]["user_id"] is None and by["DQM-WAU-001"]["sa_count"] == 1  # code on an SA, no account yet

    # the tablet of FM-WAU-001 sees one SA before the move
    device = str(uuid.uuid4())
    data = login(client, "fm-wau-001", "Password123", device)
    headers = auth(data["access_token"])
    assert client.post("/api/v1/devices/register", json={"device_id": device, "model": "T", "android_version": "13", "app_version": "0.3.0"}, headers=headers).status_code == 200
    pull = client.get(f"/api/v1/sync/pull?device_id={device}", headers=headers).json()
    assert {t["code"] for t in pull["reference"]["teams"]} == {"WAU-SA01"}

    # move WAU-SA02 (FM-WAU-002 / DQM-WAU-002) to FM-WAU-001, DQM kept
    r = client.patch("/api/v1/admin/reference/workload/assign", json={"team_ids": [teams["WAU-SA02"]["id"]], "monitor_code": "fm-wau-001"}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()[0]["monitor_code"] == "FM-WAU-001" and r.json()[0]["dqm_code"] == "DQM-WAU-002"
    pull2 = client.get(f"/api/v1/sync/pull?device_id={device}&reference_version={pull['reference_version']}", headers=headers).json()
    assert pull2["reference"] is not None and {t["code"] for t in pull2["reference"]["teams"]} == {"WAU-SA01", "WAU-SA02"}

    # another district's officer is refused, so is a DQM code in the Field Monitor slot, and mixed districts
    r = client.patch("/api/v1/admin/reference/workload/assign", json={"team_ids": [teams["WAU-SA01"]["id"]], "monitor_code": "FM-WAR-001"}, headers=admin)
    assert r.status_code == 400 and "district" in r.json()["detail"].lower(), r.text
    r = client.patch("/api/v1/admin/reference/workload/assign", json={"team_ids": [teams["WAU-SA01"]["id"]], "monitor_code": "DQM-WAU-002"}, headers=admin)
    assert r.status_code == 400
    r = client.patch("/api/v1/admin/reference/workload/assign", json={"team_ids": [teams["WAU-SA01"]["id"], teams["WAR-SA01"]["id"]], "dqm_code": "DQM-WAU-002"}, headers=admin)
    assert r.status_code == 400 and "one district" in r.json()["detail"]

    # a district DQM has no right to reassign; the audit log records the change
    dqm = auth(login(client, "dqm-wau-002", "Password123")["access_token"])
    assert client.patch("/api/v1/admin/reference/workload/assign", json={"team_ids": [teams["WAU-SA01"]["id"]], "dqm_code": "DQM-WAU-002"}, headers=dqm).status_code == 403
    log = client.get("/api/v1/admin/audit?action=workload.assign", headers=admin).json()
    entries = log["items"] if isinstance(log, dict) else log
    assert entries and entries[0]["action"] == "workload.assign"


def test_create_accounts_from_workload(client, admin, geo):
    """One click creates every officer account the workload names, with the role from the code and the district scope."""
    r = client.post("/api/v1/admin/reference/workload/accounts", headers=admin)
    assert r.status_code == 400  # nothing loaded yet
    _import_workload(client, admin)
    r = client.post("/api/v1/admin/reference/workload/accounts", headers=admin)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["existing"] == 0 and len(res["created"]) == 6
    by = {c["staff_code"]: c for c in res["created"]}
    assert by["FM-WAU-001"]["role"] == "FIELD_MONITOR" and by["FM-WAU-001"]["district"] == "Western Area Urban" and by["FM-WAU-001"]["username"] == "fm-wau-001"
    assert by["DQM-WAR-001"]["role"] == "DISTRICT_DQM" and len(by["DQM-WAR-001"]["password"]) == 10
    # the Field Monitor can sign in with the code (any case) and gets only their SA; the DQM has the district rights
    data = login(client, "FM-WAU-001", by["FM-WAU-001"]["password"])
    assert data["user"]["assigned_sas"] == 1 and "sync.use" in data["user"]["permissions"]
    dqm = login(client, "dqm-wau-001", by["DQM-WAU-001"]["password"])
    assert dqm["user"]["district_ids"] == [geo["districts"]["WAU"]["id"]] and "daily_reports.create" in dqm["user"]["permissions"]
    # repeating creates nothing new; the officers list now shows the accounts
    again = client.post("/api/v1/admin/reference/workload/accounts", headers=admin).json()
    assert again["created"] == [] and again["existing"] == 6
    offs = {o["staff_code"]: o for o in client.get(f"/api/v1/admin/reference/officers?district_id={geo['districts']['WAU']['id']}", headers=admin).json()}
    assert offs["DQM-WAU-002"]["user_id"] is not None


def test_create_officer_pair(client, admin, geo):
    """User management creates a linked Field Monitor + DQM pair: same number, staff code = username, district scope."""
    _import_workload(client, admin)  # WAU already has officers 001 and 002 on its SAs
    wau = geo["districts"]["WAU"]["id"]
    r = client.post("/api/v1/admin/users/officer-pair", json={"district_id": wau}, headers=admin)
    assert r.status_code == 201, r.text
    pair = r.json()
    assert pair["field_monitor"]["staff_code"] == "FM-WAU-003" and pair["dqm"]["staff_code"] == "DQM-WAU-003"
    assert pair["field_monitor"]["username"] == "fm-wau-003" and pair["sa_count"] == 0
    # signs in with the code in any case; role and district come from the code and the choice
    fm = login(client, "FM-WAU-003", pair["field_monitor"]["password"])
    assert fm["user"]["role"] == "FIELD_MONITOR" and fm["user"]["district_ids"] == [wau] and fm["user"]["full_name"] == "FM-WAU-003"
    dqm = login(client, "dqm-wau-003", pair["dqm"]["password"])
    assert dqm["user"]["role"] == "DISTRICT_DQM" and dqm["user"]["staff_code"] == "DQM-WAU-003"
    # a chosen number that is taken is refused; names and phones are optional and kept when given
    assert client.post("/api/v1/admin/users/officer-pair", json={"district_id": wau, "number": 3}, headers=admin).status_code == 409
    r = client.post("/api/v1/admin/users/officer-pair", json={"district_id": wau, "number": 10, "fm_full_name": "Aminata Sesay", "dqm_phone": "076123456"}, headers=admin)
    assert r.status_code == 201, r.text
    users = {u["username"]: u for u in client.get("/api/v1/admin/users", headers=admin).json()}
    assert users["fm-wau-010"]["full_name"] == "Aminata Sesay" and users["dqm-wau-010"]["phone"] == "076123456"
    # the pair now appears in the district's officer list, so SAs can be reassigned to it
    offs = {o["staff_code"] for o in client.get(f"/api/v1/admin/reference/officers?district_id={wau}", headers=admin).json()}
    assert {"FM-WAU-003", "DQM-WAU-003", "FM-WAU-010", "DQM-WAU-010"} <= offs


def test_csv_import_from_the_user_template(client, admin, geo):
    """The populated template: workbook IDs as usernames, region filled in; district roles stay scoped to their district."""
    _import_workload(client, admin)
    csv_text = (
        "username,password,full_name,phone,role,districts,region,staff_code\n"
        "FM-WAU-001,ChangeMe123,Field Monitor Western Area Urban 001,23277000000,FIELD_MONITOR,Western Area Urban,Western,FM-WAU-001\n"
        "DQM-WAU-001,ChangeMe123,District DQM Western Area Urban 001,23277000000,DISTRICT_DQM,Western Area Urban,Western,DQM-WAU-001\n"
    )
    r = client.post("/api/v1/admin/users/import", files={"file": ("users-workload.csv", csv_text, "text/csv")}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 2 and r.json()["errors"] == []
    fm = login(client, "FM-WAU-001", "ChangeMe123")["user"]
    assert fm["full_name"] == "Field Monitor Western Area Urban 001" and fm["phone"] == "23277000000"
    assert fm["district_ids"] == [geo["districts"]["WAU"]["id"]]  # the region column did not widen the scope
    assert fm["staff_code"] == "FM-WAU-001" and fm["assigned_sas"] == 1
    dqm = login(client, "dqm-wau-001", "ChangeMe123")["user"]
    assert dqm["district_ids"] == [geo["districts"]["WAU"]["id"]] and dqm["assigned_sas"] == 1
