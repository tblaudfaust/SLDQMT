"""M&E Field Monitoring, stage 1: roles and scoped access, active dates, forced password change,
frame import with chiefdoms, sections and the 10-digit EA code, preview before apply, frame versions."""

from datetime import date, timedelta

from tests.conftest import auth, login

FRAME_CSV = (
    "Region,District Code,District,Chiefdom Code,Chiefdom,Section Code,Section,SA Code,SA Name,Supervisor,EA Code,POP EA Code,EA Name,Locality,Households,Latitude,Longitude,Loc Status\n"
    "Western,WAU,Western Area Urban,52001,Central One,5200101,Tower Hill,WAU-SA01,Central 1,Mohamed Kamara,WAU-SA01-EA01,5200100101,Tower Hill A,Tower Hill,120,8.4847,-13.2296,2\n"
    "Western,WAU,Western Area Urban,52001,Central One,5200101,Tower Hill,WAU-SA01,Central 1,Mohamed Kamara,WAU-SA01-EA02,5200100102,Tower Hill B,Tower Hill,95,8.4850,-13.2300,2\n"
    "Western,WAR,Western Area Rural,51001,Waterloo,5100101,Waterloo Town,WAR-SA01,Waterloo 1,Aminata Bangura,WAR-SA01-EA01,5100100101,Waterloo A,Waterloo,140,8.3380,-13.0710,1\n"
)


def officer(client, admin, username, role, district_ids=None, region_ids=None, **extra):
    body = {"username": username, "password": "Password123", "full_name": username, "role": role, "district_ids": district_ids or [], "region_ids": region_ids or [], **extra}
    r = client.post("/api/v1/admin/users", json=body, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()


def test_frame_import_with_chiefdoms_sections_and_preview(client, admin, geo):
    # preview first: nothing is saved
    r = client.post("/api/v1/admin/reference/import?dry_run=true", files={"file": ("frame.csv", FRAME_CSV, "text/csv")}, headers=admin)
    assert r.status_code == 200, r.text
    preview = r.json()
    assert preview["dry_run"] is True and preview["chiefdoms"] == 2 and preview["sections"] == 2 and preview["eas"] == 0  # the three EAs already exist from the geo fixture
    assert preview["removed"] == {"teams": 0, "eas": 0, "team_codes": [], "ea_codes": []}
    me = auth(login(client, "admin", "adminpass123")["access_token"])
    assert client.get("/api/v1/mefm/overview", headers=me).json()["totals"]["chiefdoms"] == 0
    assert len(client.get("/api/v1/admin/reference/frame-versions", headers=admin).json()) == 1  # the geo fixture's own import

    # apply: geography created, EA carries the 10-digit code and the frame attributes, a version is recorded
    r = client.post("/api/v1/admin/reference/import", files={"file": ("frame.csv", FRAME_CSV, "text/csv")}, headers=admin)
    assert r.status_code == 200, r.text
    applied = r.json()
    assert applied["dry_run"] is False and applied["chiefdoms"] == 2 and applied["sections"] == 2
    overview = client.get("/api/v1/mefm/overview", headers=me).json()
    assert overview["scope"] == "national" and overview["totals"] == {"chiefdoms": 2, "sections": 2, "sas": 2, "eas": 3, "eas_with_point": 3, "districts": 2}
    versions = client.get("/api/v1/admin/reference/frame-versions", headers=admin).json()
    assert len(versions) == 2 and versions[0]["filename"] == "frame.csv" and versions[0]["counts"]["chiefdoms"] == 2 and versions[0]["applied_by"] == "System Administrator"

    # re-applying the same file changes nothing; a file that drops an EA reports it as removed but keeps it
    again = client.post("/api/v1/admin/reference/import?dry_run=true", files={"file": ("frame.csv", FRAME_CSV, "text/csv")}, headers=admin).json()
    assert again["chiefdoms"] == 0 and again["sections"] == 0 and again["eas"] == 0 and again["updated"] == 0
    shorter = "\n".join(FRAME_CSV.split("\n")[:3]) + "\n"  # only the two WAU EAs
    partial = client.post("/api/v1/admin/reference/import?dry_run=true", files={"file": ("frame.csv", shorter, "text/csv")}, headers=admin).json()
    assert partial["removed"]["teams"] == 0 and partial["removed"]["eas"] == 0  # WAR not touched by this file, so nothing is reported for it
    renamed = FRAME_CSV.replace("Tower Hill A", "Tower Hill Alpha")
    assert client.post("/api/v1/admin/reference/import?dry_run=true", files={"file": ("frame.csv", renamed, "text/csv")}, headers=admin).json()["updated"] == 1


def test_district_officer_sees_only_their_district(client, admin, geo):
    client.post("/api/v1/admin/reference/import", files={"file": ("frame.csv", FRAME_CSV, "text/csv")}, headers=admin)
    wau, war = geo["districts"]["WAU"]["id"], geo["districts"]["WAR"]["id"]
    regions = client.get("/api/v1/admin/reference/regions", headers=admin).json()
    western = next(r["id"] for r in regions if r["name"] == "Western")
    officer(client, admin, "me.wau", "ME_DISTRICT", district_ids=[wau])
    officer(client, admin, "me.west", "ME_REGIONAL", region_ids=[western])

    d = login(client, "me.wau", "Password123")
    assert d["user"]["role"] == "ME_DISTRICT" and d["user"]["district_ids"] == [wau] and d["user"]["must_change_password"] is True
    perms = set(d["user"]["permissions"])
    assert {"mefm.collect", "mefm.view", "sync.use"} <= perms and "mefm.review" not in perms and "dashboard.view" not in perms
    dh = auth(d["access_token"])
    ov = client.get("/api/v1/mefm/overview", headers=dh).json()
    assert ov["scope"] == "Western Area Urban" and [x["district"] for x in ov["districts"]] == ["Western Area Urban"]
    assert ov["totals"]["eas"] == 2 and ov["totals"]["chiefdoms"] == 1
    # the other district's data is not reachable through other scoped endpoints either
    assert client.get("/api/v1/dashboard/summary", headers=dh).status_code == 403  # no dashboard right at all
    wl = client.get("/api/v1/admin/reference/workload", headers=dh)
    assert wl.status_code in (200, 403)
    if wl.status_code == 200:
        assert all(r["district_id"] == wau for r in wl.json())

    rh = auth(login(client, "me.west", "Password123")["access_token"])
    ov = client.get("/api/v1/mefm/overview", headers=rh).json()
    assert ov["scope"] == "region: Western" and {x["district"] for x in ov["districts"]} == {"Western Area Urban", "Western Area Rural"}
    assert "mefm.review" in login(client, "me.west", "Password123")["user"]["permissions"]
    # an officer reassigned to another district sees that district from then on
    r = client.patch(f"/api/v1/admin/users/{d['user']['id']}", json={"district_ids": [war]}, headers=admin)
    assert r.status_code == 200
    dh2 = auth(login(client, "me.wau", "Password123")["access_token"])
    assert client.get("/api/v1/mefm/overview", headers=dh2).json()["scope"] == "Western Area Rural"


def test_active_dates_and_forced_password_change(client, admin, geo):
    wau = geo["districts"]["WAU"]["id"]
    today = date.today()
    officer(client, admin, "me.future", "ME_DISTRICT", district_ids=[wau], active_from=(today + timedelta(days=3)).isoformat())
    officer(client, admin, "me.past", "ME_DISTRICT", district_ids=[wau], active_until=(today - timedelta(days=1)).isoformat())
    officer(client, admin, "me.now", "ME_DISTRICT", district_ids=[wau], active_from=today.isoformat(), active_until=(today + timedelta(days=30)).isoformat())
    r = client.post("/api/v1/auth/login", json={"username": "me.future", "password": "Password123"})
    assert r.status_code == 403 and "active from" in r.json()["detail"]
    r = client.post("/api/v1/auth/login", json={"username": "me.past", "password": "Password123"})
    assert r.status_code == 403 and "expired" in r.json()["detail"]
    d = login(client, "me.now", "Password123")
    assert d["user"]["must_change_password"] is True
    h = auth(d["access_token"])
    assert client.post("/api/v1/auth/change-password", json={"current_password": "Password123", "new_password": "NewSecret456"}, headers=h).status_code == 204
    assert login(client, "me.now", "NewSecret456")["user"]["must_change_password"] is False
    # an administrator's password reset forces a change again; the CSV import sets the flag and the dates
    uid = d["user"]["id"]
    assert client.post(f"/api/v1/admin/users/{uid}/reset-password", json={"password": "Temporary789"}, headers=admin).status_code == 200
    assert login(client, "me.now", "Temporary789")["user"]["must_change_password"] is True
    csv_text = "username,password,full_name,phone,role,districts,region,active_from,active_until\nme.csv,Password123,CSV Officer,076000000,ME_DISTRICT,Western Area Urban,,2026-10-01,2026-12-31\n"
    r = client.post("/api/v1/admin/users/import", files={"file": ("u.csv", csv_text, "text/csv")}, headers=admin)
    assert r.status_code == 200 and r.json()["created"] == 1, r.text
    u = next(x for x in client.get("/api/v1/admin/users?role=ME_DISTRICT", headers=admin).json() if x["username"] == "me.csv")
    assert u["active_from"] == "2026-10-01" and u["active_until"] == "2026-12-31" and u["must_change_password"] is True
