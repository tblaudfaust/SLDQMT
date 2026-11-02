"""ToT practice set: load assigns the practice workload and creates shared-password accounts scoped by their SAs;
the practice officer signs in without a forced password change and sees exactly their SAs; remove cleans up."""
import io

from openpyxl import Workbook

from app.services import tot_practice
from tests.conftest import login


def _workbook(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "FIELD_MONITOR"
    ws.append(["REG_NAME", "DIST_NAME", "DIST_CODE", "CHFDM_NAME", "CHFDM_CODE", "SA_NAME", "SA_CODE", "SUP_ID", "NO_OF_EAS", "NO_OF_SECTIONS",
               "Venue", "Hall", "Hall name", "Workload", "DQM ID", "Field monitor ID"])
    ws.append(["WESTERN", "WESTERN URBAN", "WAU", "CENTRAL I", "52901", "Central 1", "WAU-SA01", "529010100100", 5, 1, "WAU", 1, "YWCA Hall 1", 1, "DQM-WAU-H1-01", "FM-WAU-H1-01"])
    ws.append(["WESTERN", "WESTERN RURAL", "WAR", "KOYA", "51901", "Waterloo 1", "WAR-SA01", "519010100100", 4, 1, "WAU", 1, "YWCA Hall 1", 1, "DQM-WAU-H1-01", "FM-WAU-H1-01"])
    ws.append(["WESTERN", "WESTERN URBAN", "WAU", "CENTRAL I", "52901", "Central 2", "WAU-SA02", "529010100200", 6, 1, "WAU", 1, "YWCA Hall 1", 2, "DQM-WAU-H1-02", None])
    p = tmp_path / "tot_practice_workload.xlsx"
    wb.save(p)
    return p


def test_practice_codes_and_names():
    assert tot_practice.is_practice_code("DQM-WAU-H1-01") and tot_practice.is_practice_code("fm-plo-h3-35")
    assert not tot_practice.is_practice_code("FM-Bo-001") and not tot_practice.is_practice_code("DQM-11-007")
    assert tot_practice.full_name("FM-BOM-H2-07") == "Field Monitor Makeni hall 2 seat 7"


def test_load_sign_in_scope_and_remove(client, admin, geo, tmp_path, monkeypatch):
    path = _workbook(tmp_path)
    monkeypatch.setattr(tot_practice, "WORKBOOK", path)
    # a real officer account must not be touched by load/remove
    r = client.post("/api/v1/admin/users", json={"username": "fm.real", "password": "Password123", "full_name": "Real FM", "role": "FIELD_MONITOR", "district_ids": [geo["districts"]["WAU"]["id"]]}, headers=admin)
    assert r.status_code == 201, r.text
    s = client.get("/api/v1/admin/reference/practice", headers=admin).json()
    assert s["loaded"] is False and s["sas_assigned"] == 0

    r = client.post("/api/v1/admin/reference/practice", json={"dqm_password": "short", "fm_password": "FmClass2026"}, headers=admin)
    assert r.status_code == 422
    r = client.post("/api/v1/admin/reference/practice", json={"dqm_password": "DqmClass2026", "fm_password": "FmClass2026"}, headers=admin)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["sas_assigned"] == 3 and out["accounts_created"] == 3 and out["dqm_accounts"] == 2 and out["fm_accounts"] == 1 and out["unknown_districts"] == []

    # the practice FM signs in with the shared password, is not forced to change it, and sees exactly its two SAs
    data = login(client, "FM-WAU-H1-01", "FmClass2026")
    assert data["user"]["must_change_password"] in (False, None)
    assert data["user"]["staff_code"] == "FM-WAU-H1-01" and data["user"]["assigned_sas"] == 2
    assert sorted(data["user"]["district_ids"]) == sorted([geo["districts"]["WAU"]["id"], geo["districts"]["WAR"]["id"]])
    dqm = login(client, "dqm-wau-h1-02", "DqmClass2026")["user"]
    assert dqm["role"] == "DISTRICT_DQM" and dqm["assigned_sas"] == 1 and dqm["district_ids"] == [geo["districts"]["WAU"]["id"]]

    s = client.get("/api/v1/admin/reference/practice", headers=admin).json()
    assert s == {"loaded": True, "dqm_accounts": 2, "fm_accounts": 1, "sas_assigned": 3, "logged_in": 2, "workbook": path.name}

    # loading again keeps the accounts; with reset_passwords the password changes
    r = client.post("/api/v1/admin/reference/practice", json={"dqm_password": "NewDqmPass1", "fm_password": "NewFmPass1", "reset_passwords": True}, headers=admin)
    assert r.status_code == 200 and r.json()["accounts_created"] == 0 and r.json()["accounts_updated"] == 3
    assert client.post("/api/v1/auth/login", json={"username": "FM-WAU-H1-01", "password": "FmClass2026"}).status_code == 401
    login(client, "FM-WAU-H1-01", "NewFmPass1")

    # a plain user manager without reference.manage may not load
    r = client.post("/api/v1/admin/users", json={"username": "dqm.nat", "password": "Password123", "full_name": "N", "role": "NATIONAL_DQM", "district_ids": []}, headers=admin)
    assert r.status_code == 201, r.text

    r = client.delete("/api/v1/admin/reference/practice", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["accounts"] == 3 and r.json()["sas_cleared"] == 3
    assert client.post("/api/v1/auth/login", json={"username": "FM-WAU-H1-01", "password": "NewFmPass1"}).status_code == 401
    login(client, "fm.real", "Password123")   # the real account is untouched
    s = client.get("/api/v1/admin/reference/practice", headers=admin).json()
    assert s["loaded"] is False and s["sas_assigned"] == 0


def test_shipped_workbook_is_consistent():
    officers = tot_practice.read_officers()
    assert len(officers) == 1363
    assert sum(1 for c in officers if c.startswith("DQM-")) == 689 and sum(1 for c in officers if c.startswith("FM-")) == 674
    assert all(tot_practice.is_practice_code(c) for c in officers)
    assert io  # keep the import used for editors that strip it


def test_startup_hook_loads_once_on_production(client, admin, geo, tmp_path, monkeypatch):
    from app.core.config import settings
    from app.core.security import hash_password
    from app.db.session import SessionLocal

    monkeypatch.setattr(tot_practice, "WORKBOOK", _workbook(tmp_path))
    monkeypatch.setattr(tot_practice, "PRACTICE_HASHES", {"DISTRICT_DQM": hash_password("DqmHook2026"), "FIELD_MONITOR": hash_password("FmHook2026")})
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    db = SessionLocal()
    try:
        first = tot_practice.ensure_practice_loaded(db)
        assert first and first["accounts_created"] == 3
        assert tot_practice.ensure_practice_loaded(db) is None   # marker set: not again
    finally:
        db.close()
    login(client, "FM-WAU-H1-01", "FmHook2026")
    login(client, "DQM-WAU-H1-01", "DqmHook2026")
