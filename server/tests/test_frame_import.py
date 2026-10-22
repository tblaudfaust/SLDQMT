import io

from openpyxl import Workbook

from app.services.import_service import clean_name


def make_frame() -> bytes:
    """A miniature GIS district workbook with the two sheets the importer reads."""
    wb = Workbook()
    sa = wb.active
    sa.title = "SUPERVISORY_AREA"
    sa.append(["OBJECTID", "REG_NAME", "REG_CODE", "DIST_NAME", "DIST_NO", "DIST_CODE", "LC_CC_NAME", "LC_CC_NO", "LC_CC_CODE", "CHFDM_NAME", "CHFDM_NO", "CHFDM_CODE", "SA_NAME", "SA_NO", "SA_CODE", "SUP_ID", "NO_OF_EAS", "NO_OF_SECTIONS", "SUPERVISOR"])
    sa.append([1, "NORTHERN", "2", "FALABA", "2", "22", "FALABA", "9", "229", "DELEMANDUGU", "01", "22901", "MADULFORAYA_COMMUNITY_MOSQUE_", "001", "22901001", "229010100100", 2, 1, "1961"])
    sa.append([2, "NORTHERN", "2", "FALABA", "2", "22", "FALABA", "9", "229", "DELEMANDUGU", "01", "22901", "MCA_CHURCH_TAMBAIABALIA_", "002", "22901002", "229010100200", 1, 1, "1962"])
    ea = wb.create_sheet("ENUMERATION_AREA")
    ea.append(["OBJECTID", "REG_NAME", "REG_CODE", "DIST_NAME", "DIST_CODE", "CHFDM_NAME", "SA_NAME", "SA_CODE", "LOC_NAME", "EA_NAME", "EA_NO", "EA_CODE", "TOT_HH", "LONGITUDE", "LATITUDE", "ENUM_ID", "SUP_ID", "ENUMERATOR", "SUPERVISOR"])
    # EA 1 spans two localities -> two rows, one EA
    ea.append([1, "NORTHERN", "2", "FALABA", "22", "DELEMANDUGU", "MADULFORAYA_COMMUNITY_MOSQUE_", "22901001", "BILIMAIA", "MADULFORAYA_COMMUNITY_MOSQUE_", "001", "229010130011", 98, "-11.018", "9.363", "229010100101", "229010100100", "006011", "1961"])
    ea.append([2, "NORTHERN", "2", "FALABA", "22", "DELEMANDUGU", "MADULFORAYA_COMMUNITY_MOSQUE_", "22901001", "MANDOLOFORIA", "MADULFORAYA_COMMUNITY_MOSQUE_", "001", "229010130011", 98, "-11.017", "9.363", "229010100101", "229010100100", "006011", "1961"])
    ea.append([3, "NORTHERN", "2", "FALABA", "22", "DELEMANDUGU", "MADULFORAYA_COMMUNITY_MOSQUE_", "22901001", "FAYIYA", "CRS_STORE_FAYIYA", "002", "229010110021", 104, "-10.990", "9.331", "229010100201", "229010100100", "006012", "1961"])
    ea.append([4, "NORTHERN", "2", "FALABA", "22", "DELEMANDUGU", "MCA_CHURCH_TAMBAIABALIA_", "22901002", "TAMBAIA", "MCA_CHURCH_TAMBAIABALIA_", "001", "229010230011", 60, "-10.95", "9.30", "229010200101", "229010100200", "006021", "1962"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_clean_name():
    assert clean_name("MADULFORAYA_COMMUNITY_MOSQUE_") == "Madulforaya Community Mosque"
    assert clean_name("WESTERN URBAN") == "Western Urban"
    assert clean_name("Mohamed Kamara") == "Mohamed Kamara"
    assert clean_name("") is None


def test_frame_workbook_import(client, admin):
    r = client.post("/api/v1/admin/reference/import", files={"file": ("FALABA_EA_FRAME_11_09_2026.xlsx", make_frame(), "application/octet-stream")}, headers=admin)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["regions"] == 1 and res["districts"] == 1
    assert res["teams"] == 2
    assert res["supervisors"] == 2
    assert res["enumerators"] == 3
    assert res["eas"] == 3  # the two-locality EA counted once
    assert res["warnings"] == []

    districts = client.get("/api/v1/admin/reference/districts", headers=admin).json()
    assert districts[0]["name"] == "Falaba" and districts[0]["code"] == "22"
    teams = client.get("/api/v1/admin/reference/teams", headers=admin).json()
    t1 = next(t for t in teams if t["code"] == "22901001")
    assert t1["name"] == "Madulforaya Community Mosque"
    assert t1["chiefdom"] == "Delemandugu" and t1["ea_count"] == 2
    sups = client.get(f"/api/v1/admin/reference/supervisors?team_id={t1['id']}", headers=admin).json()
    assert sups[0]["name"] == "Supervisor 1961" and sups[0]["code"] == "1961"
    eas = client.get(f"/api/v1/admin/reference/eas?team_id={t1['id']}", headers=admin).json()
    assert {e["code"] for e in eas} == {"229010130011", "229010110021"}
    first = next(e for e in eas if e["code"] == "229010130011")
    assert first["locality"] == "Bilimaia" and first["households"] == 98 and first["lat"] == 9.363
    # each EA is linked to the enumerator of its frame row, so the tablet can pick the EA from the enumerator
    enums = {e["id"]: e for e in client.get(f"/api/v1/admin/reference/enumerators?team_id={t1['id']}", headers=admin).json()}
    assert all(e["enumerator_id"] in enums for e in eas) and len({e["enumerator_id"] for e in eas}) == 2

    # Re-import: nothing new, names unchanged, ids stable
    r2 = client.post("/api/v1/admin/reference/import", files={"file": ("FALABA_EA_FRAME_11_09_2026.xlsx", make_frame(), "application/octet-stream")}, headers=admin)
    assert r2.json()["teams"] == 0 and r2.json()["eas"] == 0
    assert client.get("/api/v1/admin/reference/teams", headers=admin).json()[0]["id"] == teams[0]["id"]


def test_shipped_enumerator_links_backfill(client, admin):
    """EAs imported without their enumerator get it from the shipped mapping (SA code -> EA code -> enumerator code)."""
    from app.db.session import SessionLocal
    from app.models import Enumerator, EnumerationArea, Setting
    from app.services import ea_links

    assert client.post("/api/v1/admin/reference/import", files={"file": ("FALABA_EA_FRAME_11_09_2026.xlsx", make_frame(), "application/octet-stream")}, headers=admin).status_code == 200
    db = SessionLocal()
    try:
        eas = db.query(EnumerationArea).all()
        wanted = {}
        for ea in eas:
            wanted[(ea.team.code, ea.code)] = db.get(Enumerator, ea.enumerator_id).code if ea.enumerator_id else None
            ea.enumerator_id = None
        db.commit()
        mapping = {}
        for (sa, code), en in wanted.items():
            if en:
                mapping.setdefault(sa, {})[code] = en
        counts = ea_links.apply_links(db, mapping)
        db.commit()
        assert counts["linked"] == sum(1 for v in wanted.values() if v) and counts["no_enumerator"] == 0
        assert all(ea.enumerator_id is not None for ea in db.query(EnumerationArea).all())
        # the start-up hook already ran when the app started (marker set); it runs once per data version
        assert db.get(Setting, ea_links.MARKER).value == ea_links.VERSION and ea_links.ensure_links(db) is None
        assert ea_links.load_mapping() and len(ea_links.load_mapping()) > 4000  # the national frames
    finally:
        db.close()


def test_names_can_be_added_afterwards(client, admin):
    client.post("/api/v1/admin/reference/import", files={"file": ("FALABA_EA_FRAME_11_09_2026.xlsx", make_frame(), "application/octet-stream")}, headers=admin)
    csv = "District Code,SA Code,Supervisor Code,Supervisor,Supervisor Phone\n22,22901001,1961,Mohamed Kamara,+23276000000\n"
    r = client.post("/api/v1/admin/reference/import", files={"file": ("names.csv", csv, "text/csv")}, headers=admin)
    assert r.status_code == 200 and r.json()["supervisors"] == 0
    teams = client.get("/api/v1/admin/reference/teams", headers=admin).json()
    t1 = next(t for t in teams if t["code"] == "22901001")
    sups = client.get(f"/api/v1/admin/reference/supervisors?team_id={t1['id']}", headers=admin).json()
    assert sups[0]["name"] == "Mohamed Kamara" and sups[0]["phone"] == "+23276000000"


def test_shipped_workload_distribution(client, admin):
    """The shipped workload sets the Field Monitor and DQM of every SA it lists and clears SAs it dropped."""
    from app.db.session import SessionLocal
    from app.models import Setting, Team
    from app.services import workload_data

    assert client.post("/api/v1/admin/reference/import", files={"file": ("FALABA_EA_FRAME_11_09_2026.xlsx", make_frame(), "application/octet-stream")}, headers=admin).status_code == 200
    db = SessionLocal()
    try:
        t2 = db.query(Team).filter(Team.code == "22901002").one()
        t2.monitor_code, t2.dqm_code = "FM-Fal-009", "DQM-Fal-009"  # an old assignment the new file no longer has
        db.commit()
        counts = workload_data.apply_workload(db, {"22901001": {"fm": "FM-22-001", "dqm": "DQM-22-001"}, "99999999": {"fm": "FM-22-002", "dqm": "DQM-22-002"}})
        db.commit()
        t1 = db.query(Team).filter(Team.code == "22901001").one()
        assert (t1.monitor_code, t1.dqm_code) == ("FM-Fal-001", "DQM-Fal-001")  # canonical district abbreviation
        db.refresh(t2)
        assert t2.monitor_code is None and t2.dqm_code is None
        assert counts == {"assigned": 1, "unchanged": 0, "cleared": 1, "unknown_sa": 1}
        # the start-up hook already applied the shipped file once (marker), and the file covers the whole country
        assert db.get(Setting, workload_data.MARKER).value == workload_data.VERSION and workload_data.ensure_workload(db) is None
        shipped = workload_data.load_mapping()
        assert len(shipped) > 4700 and len({v["fm"] for v in shipped.values()}) == 486 and all(v["dqm"].startswith("DQM-") for v in shipped.values())
    finally:
        db.close()
