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

    # Re-import: nothing new, names unchanged, ids stable
    r2 = client.post("/api/v1/admin/reference/import", files={"file": ("FALABA_EA_FRAME_11_09_2026.xlsx", make_frame(), "application/octet-stream")}, headers=admin)
    assert r2.json()["teams"] == 0 and r2.json()["eas"] == 0
    assert client.get("/api/v1/admin/reference/teams", headers=admin).json()[0]["id"] == teams[0]["id"]


def test_names_can_be_added_afterwards(client, admin):
    client.post("/api/v1/admin/reference/import", files={"file": ("FALABA_EA_FRAME_11_09_2026.xlsx", make_frame(), "application/octet-stream")}, headers=admin)
    csv = "District Code,SA Code,Supervisor Code,Supervisor,Supervisor Phone\n22,22901001,1961,Mohamed Kamara,+23276000000\n"
    r = client.post("/api/v1/admin/reference/import", files={"file": ("names.csv", csv, "text/csv")}, headers=admin)
    assert r.status_code == 200 and r.json()["supervisors"] == 0
    teams = client.get("/api/v1/admin/reference/teams", headers=admin).json()
    t1 = next(t for t in teams if t["code"] == "22901001")
    sups = client.get(f"/api/v1/admin/reference/supervisors?team_id={t1['id']}", headers=admin).json()
    assert sups[0]["name"] == "Mohamed Kamara" and sups[0]["phone"] == "+23276000000"
