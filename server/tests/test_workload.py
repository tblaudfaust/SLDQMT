"""Workload assignment: SAs carry Field Monitor / DQM codes, accounts link by staff code,
tablets receive only their own SAs and a DQM's dashboard defaults to their own SAs."""

import uuid

from tests.conftest import auth, login, make_error

WORKLOAD_CSV = (
    "Region,District,SA code,SA name,Field monitor ID,DQM ID\n"
    "Western,Western Area Urban,WAU-SA01,Central 1,FM-51-001,DQM-51-001\n"
    "Western,Western Area Urban,WAU-SA02,Central 2,FM-51-002,DQM-51-002\n"
    "Western,Western Area Rural,WAR-SA01,Waterloo 1,FM-52-001,DQM-52-001\n"
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
    assert teams["WAU-SA01"]["monitor_code"] == "FM-51-001" and teams["WAU-SA01"]["dqm_code"] == "DQM-51-001"
    assert teams["WAR-SA01"]["monitor_code"] == "FM-52-001"
    # re-import is idempotent
    assert _import_workload(client, admin)["teams"] == 0
    rows = client.get("/api/v1/admin/reference/workload?search=FM-51", headers=admin).json()
    assert {r["code"] for r in rows} == {"WAU-SA01", "WAU-SA02"}
    assert rows[0]["monitor_name"] is None  # no account yet


def test_field_monitor_bundle_is_limited_to_own_sas(client, admin, geo):
    _import_workload(client, admin)
    wau = geo["districts"]["WAU"]["id"]
    body = {"username": "fm-51-001", "password": "Password123", "full_name": "Field Monitor FM-51-001", "role": "FIELD_MONITOR", "district_ids": [wau], "staff_code": "fm-51-001"}
    r = client.post("/api/v1/admin/users", json=body, headers=admin)
    assert r.status_code == 201, r.text
    assert r.json()["staff_code"] == "FM-51-001"
    device = str(uuid.uuid4())
    data = login(client, "fm-51-001", "Password123", device)
    assert data["user"]["assigned_sas"] == 1 and data["user"]["staff_code"] == "FM-51-001"
    headers = auth(data["access_token"])
    assert client.post("/api/v1/devices/register", json={"device_id": device, "model": "Test tablet", "android_version": "13", "app_version": "0.3.0"}, headers=headers).status_code == 200
    pr = client.get(f"/api/v1/sync/pull?device_id={device}", headers=headers)
    assert pr.status_code == 200, pr.text
    pull = pr.json()
    codes = {t["code"] for t in pull["reference"]["teams"]}
    assert codes == {"WAU-SA01"}  # not WAU-SA02, which belongs to FM-51-002
    assert {e["code"] for e in pull["reference"]["eas"]} == {"WAU-SA01-EA01", "WAU-SA01-EA02"}
    version = pull["reference_version"]

    # the workload page shows the account against the SA
    rows = client.get("/api/v1/admin/reference/workload?search=WAU-SA01", headers=admin).json()
    assert rows[0]["monitor_name"] == "Field Monitor FM-51-001"

    # reassigning the SA changes the bundle version so the tablet refreshes
    r = client.post("/api/v1/admin/reference/import", files={"file": ("w.csv", "District,SA code,Field monitor ID,DQM ID\nWestern Area Urban,WAU-SA02,FM-51-001,DQM-51-001\n", "text/csv")}, headers=admin)
    assert r.status_code == 200, r.text
    pull2 = client.get(f"/api/v1/sync/pull?device_id={device}&reference_version={version}", headers=headers).json()
    assert pull2["reference"] is not None and {t["code"] for t in pull2["reference"]["teams"]} == {"WAU-SA01", "WAU-SA02"}


def test_dqm_dashboard_defaults_to_own_sas(client, admin, geo, monitor):
    _import_workload(client, admin)
    wau = geo["districts"]["WAU"]["id"]
    teams = {t["code"]: t for t in client.get("/api/v1/admin/reference/teams", headers=admin).json()}
    # one error on WAU-SA01 (DQM-51-001's SA) and one on WAU-SA02 (DQM-51-002's SA)
    for code in ("WAU-SA01", "WAU-SA02"):
        err = make_error(geo, team_id=teams[code]["id"], description=f"error on {code}")
        r = client.post("/api/v1/sync/push", json={"device_id": monitor["device_id"], "errors": [err]}, headers=monitor["headers"])
        assert r.status_code == 200, r.text
        assert all(x["result"] != "rejected" for x in r.json()["receipts"]), r.text
    r = client.post("/api/v1/admin/users", json={"username": "dqm-51-001", "password": "Password123", "full_name": "DQM 51-001", "role": "DISTRICT_DQM", "district_ids": [wau], "staff_code": "DQM-51-001"}, headers=admin)
    assert r.status_code == 201, r.text
    dqm = auth(login(client, "dqm-51-001", "Password123")["access_token"])
    own = client.get("/api/v1/errors", headers=dqm).json()
    assert own["total"] == 1 and own["items"][0]["team"].startswith("WAU-SA01")
    whole = client.get("/api/v1/errors?own_sas=false", headers=dqm).json()
    assert whole["total"] == 2
