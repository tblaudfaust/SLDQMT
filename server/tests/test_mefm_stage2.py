"""M&E Field Monitoring, stage 2: the questionnaire spec with its skips, tablet sync (pull the district
frame and the form, push visits and check-ins), GPS checks, the automatic issues log and the visit reads."""

import uuid
from datetime import datetime, timedelta, timezone

from app.core import mefm_form
from tests.conftest import auth, login
from tests.test_mefm_stage1 import FRAME_CSV, officer

EA_WAU = "5200100101"  # Tower Hill A, point 8.4847,-13.2296
EA_WAR = "5100100101"


def base_answers(phase="E", **over):
    """A complete, valid form for the phase (team found, interview observed, 2 households, 3 respondents)."""
    a = {
        "A2": "2026-10-07", "A3_arrived": "09:10", "A3_left": "12:40", "A9": "1", "A11": "Sup Kamara / Enum Sesay 0012", "A12": phase, "A13": 3, "A14": "2", "A16": "1",
        "B1": "1", "B2": "1", "B3": "1", "B4": "1", "B5": "1", "B6": "1", "B7": "3", "B8": 2, "B9": "1", "B10": "2", "B12": "3",
        "C1": "1", "C2": 80, "C3": "1", "C4": "1", "C4_version": "2.3.1", "C5": "1", "C6": "1", "C7": "1", "C8": "2026-10-06", "C9": 0, "C11": "1", "C12": "2", "C13": "1", "C14": "1", "C15": "2",
        "D1": "1", "D2": "1", "D3": "1", "D4": "2", "D5": "2", "D6": "2", "D7": "2", "D8": "1", "D9": "1", "D10": 3, "D11": ["none"], "D12": "3",
        "E1": 40, "E2": 55, "E3": 120, "E4": "1", "E5": "1", "E6": "1", "E7": "1", "E8": "8", "E9": "1", "E10": "8", "E11": 6, "E12": "3",
        "F0": "1", "F1": "1", "F2": "1", "F3": "krio", "F4": "1", "F5": "1", "F6": "1", "F7": "1", "F8_start": "10:00", "F8_end": "10:35", "F9": "1", "F10": "1", "F11": "1", "F12": "1",
        "F13": "1", "F14": "1", "F15": "8", "F16": "1", "F17": "1", "F18": "1", "F19": "8", "F20": 4, "F21": "3",
        "G": [
            {"G1": "S-012", "G2": "1", "G3_match": "1", "G4_household": 6, "G4_tablet": 6, "G5_household": "3/3", "G5_match": "1", "G6": "2", "G6_match": "1", "G7_household": 45, "G7_tablet": 45, "G8": "2", "G8_match": "1", "G9": "1", "G10": "2", "G11": "4"},
            {"G1": "S-031", "G2": "1", "G3_match": "1", "G4_household": 4, "G4_tablet": 5, "G5_household": "2/2", "G5_match": "2", "G6": "1", "G6_match": "1", "G7_household": 60, "G7_tablet": 58, "G8": "2", "G8_match": "1", "G9": "1", "G10": "2", "G11": "3"},
        ],
        "H1": "1", "H2_enumerators": 5, "H2_visited": 4, "H3": "1", "H4": "1", "H5": 2, "H6": "1", "H7": "2", "H9_done": 60, "H9_expected": 120, "H10": "1", "H11": 3, "H12": "1", "H13": "1", "H14": "3", "H_flags": ["age_heaping"],
        "I": [
            {"I1": "1", "I2": "radio", "I3": "1", "I4": "1", "I5": "2", "I7": "2"},
            {"I1": "1", "I2": "crier", "I3": "2", "I5": "2", "I7": "2"},
            {"I1": "2", "I5": "2", "I7": "1"},
        ],
        "I8_present": "2", "I9_present": "2", "I10_present": "1", "I10_arrangement": "3", "I11_present": "2", "I12_present": "2",
        "J1": "3", "J2": "3", "J3": "4", "J4": "3", "J5": "4", "J6": "3", "J8": "1", "J9": "2", "J10": "Good team, map slow to open.",
    }
    a.update(over)
    return a


def test_spec_routing_and_validation():
    clean, errors = mefm_form.validate({**base_answers("E"), "A8": EA_WAU, "A15": {"lat": 8.48, "lng": -13.23, "accuracy_m": 9, "at": "2026-10-07T09:10:00Z"}})
    assert errors == [], errors
    assert "E1" not in clean and "B1" in clean and len(clean["G"]) == 2 and len(clean["I"]) == 3  # listing section skipped in enumeration
    assert "I4" in clean["I"][0] and "I4" not in clean["I"][1]  # community leader only
    assert clean["J7"] == round((3 + 3 + 4 + 3 + 4 + 3) / 6)
    # listing phase: E asked, F and G not; team not found: B to H skipped, A17 required
    clean, errors = mefm_form.validate({**base_answers("L"), "A8": EA_WAU, "A15": {"lat": 1, "lng": 1}})
    assert errors == [] and "E1" in clean and "F0" not in clean and "G" not in clean and "H1" in clean
    clean, errors = mefm_form.validate({**base_answers("E"), "A16": "2", "A8": EA_WAU, "A15": {"lat": 1, "lng": 1}})
    assert "A17: an answer is required" in errors
    clean, errors = mefm_form.validate({**base_answers("E"), "A16": "2", "A17": "5", "A17_other": "On strike", "A8": EA_WAU, "A15": {"lat": 1, "lng": 1}})
    assert errors == [] and "B1" not in clean and "H1" not in clean and "I" in clean and clean["A17_other"] == "On strike"
    # value rules
    _, errors = mefm_form.validate({**base_answers("E"), "A8": EA_WAU, "A15": {"lat": 1, "lng": 1}, "A3_left": "08:00", "C2": 140, "D11": ["none", "mining"], "H2_visited": 9, "C9": 3})
    assert "A3_left: time left must be after time arrived" in errors and "C2: at most 100" in errors and "H2_visited: cannot exceed the enumerators in the SA" in errors
    assert any(e.startswith("D11:") for e in errors) and "C10: an answer is required" in errors
    _, errors = mefm_form.validate({**base_answers("E"), "A8": EA_WAU})
    assert any(e.startswith("A15:") for e in errors)  # no GPS, no submission
    # critical issues: every flagged item coded as the problem value
    clean, _ = mefm_form.validate({**base_answers("E"), "A8": EA_WAU, "A15": {"lat": 1, "lng": 1}, "C5": "2", "C15": "1", "G": [dict(base_answers()["G"][0], G2="2"), base_answers()["G"][1]]})
    codes = [i["question"] for i in mefm_form.critical_issues(clean)]
    assert codes == ["C5", "C15", "G2"]
    ind = mefm_form.indicators(clean)
    assert ind["tablet_ready"] is False and ind["hh_visited"] == 0.5 and ind["team_in_ea"] is True and ind["synced_24h"] is True and ind["ea_good"] is True


def me_device(client, admin, geo, username="me.wau", district="WAU"):
    officer(client, admin, username, "ME_DISTRICT", district_ids=[geo["districts"][district]["id"]])
    device_id = str(uuid.uuid4())
    d = login(client, username, "Password123", device_id)
    h = auth(d["access_token"])
    r = client.post("/api/v1/devices/register", json={"device_id": device_id, "model": "Test phone", "android_version": "14", "app_version": "0.4.0"}, headers=h)
    assert r.status_code == 200, r.text
    return {"headers": h, "device_id": device_id, "user": d["user"]}


def visit(ea=EA_WAU, lat=8.4849, lng=-13.2298, acc=8.0, at="2026-10-07T09:12:00+00:00", **over):
    now = datetime(2026, 10, 7, 12, 50, tzinfo=timezone.utc)
    return {"id": str(uuid.uuid4()), "pop_ea_code": ea, "answers": base_answers(**over), "gps": {"lat": lat, "lng": lng, "accuracy_m": acc, "at": at},
            "client_created_at": now.isoformat(), "client_updated_at": now.isoformat()}


def test_pull_gives_district_frame_and_form(client, admin, geo):
    client.post("/api/v1/admin/reference/import", files={"file": ("frame.csv", FRAME_CSV, "text/csv")}, headers=admin)
    me = me_device(client, admin, geo)
    r = client.get("/api/v1/mefm/sync/pull", params={"device_id": me["device_id"]}, headers=me["headers"])
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["form"]["sections"][0]["code"] == "A" and len(p["form"]["sections"]) == 11 and p["form_version"]
    f = p["frame"]
    assert [d["code"] for d in f["districts"]] == ["WAU"] and len(f["chiefdoms"]) == 1 and len(f["sections"]) == 1
    assert sorted(e["pop_ea_code"] for e in f["eas"]) == ["5200100101", "5200100102"] and f["eas"][0]["lat"] is not None and f["eas"][0]["expected_households"] == 120
    assert f["teams"][0]["supervisor"] == "Mohamed Kamara" and len(f["teams"][0]["enumerators"]) == 2
    assert p["settings"]["mefm_ea_distance_m"] == "1000" and p["visits"] == [] and p["pin_reset"] is False
    # unchanged versions are not re-sent
    again = client.get("/api/v1/mefm/sync/pull", params={"device_id": me["device_id"], "frame_version": p["frame_version"], "form_version": p["form_version"], "cursor": p["cursor"]}, headers=me["headers"]).json()
    assert again["frame"] is None and again["form"] is None
    # a plain Field Monitor cannot use the M&E sync
    fm = client.post("/api/v1/admin/users", json={"username": "fm.x", "password": "Password123", "full_name": "FM", "role": "FIELD_MONITOR", "district_ids": [geo["districts"]["WAU"]["id"]]}, headers=admin)
    assert fm.status_code == 201
    fh = auth(login(client, "fm.x", "Password123")["access_token"])
    assert client.get("/api/v1/mefm/sync/pull", params={"device_id": me["device_id"]}, headers=fh).status_code == 403
    # an unregistered device is refused
    assert client.get("/api/v1/mefm/sync/pull", params={"device_id": str(uuid.uuid4())}, headers=me["headers"]).status_code == 403


def test_push_visits_checkins_flags_and_issues(client, admin, geo):
    client.post("/api/v1/admin/reference/import", files={"file": ("frame.csv", FRAME_CSV, "text/csv")}, headers=admin)
    me = me_device(client, admin, geo)
    good = visit()
    far = visit(lat=8.53, lng=-13.2296, acc=70.0, at="2026-10-07T21:30:00+00:00", C5="2", G=[dict(base_answers()["G"][0], G2="2"), base_answers()["G"][1]],
                J_issues=[{"question": "D4", "severity": "Major", "description": "Two new houses behind the school not on the map", "action": "Reported to GIS", "referred_to": "HQ", "deadline": "2026-10-10"}])
    other = visit(ea=EA_WAR)
    unknown = visit(ea="9999999999")
    bad = visit(A3_left="08:00")
    checkin = {"id": str(uuid.uuid4()), "section_code": "5200101", "note": "Passing through", "gps": {"lat": 8.4860, "lng": -13.2310, "accuracy_m": 10}, "at": "2026-10-07T08:00:00+00:00"}
    r = client.post("/api/v1/mefm/sync/push", json={"device_id": me["device_id"], "app_version": "0.4.0", "pending_count": 6, "visits": [good, far, other, unknown, bad], "checkins": [checkin]}, headers=me["headers"])
    assert r.status_code == 200, r.text
    p = r.json()
    rc = {x["id"]: x for x in p["receipts"]}
    assert p["applied"] == 3 and p["rejected"] == 3
    assert rc[good["id"]]["result"] == "applied" and rc[good["id"]]["flags"] == []
    assert rc[checkin["id"]]["result"] == "applied"
    assert set(rc[far["id"]]["flags"]) == {"poor_accuracy", "night", "far_from_ea"}
    assert rc[other["id"]]["reason"] == "NOT_IN_SCOPE" and rc[unknown["id"]]["reason"] == "UNKNOWN_EA"
    assert rc[bad["id"]]["reason"] == "INVALID" and "A3_left: time left must be after time arrived" in rc[bad["id"]]["errors"]

    # the same forms again: duplicates, nothing changes
    r = client.post("/api/v1/mefm/sync/push", json={"device_id": me["device_id"], "visits": [good, far]}, headers=me["headers"]).json()
    assert r["duplicates"] == 2 and r["applied"] == 0
    # a corrected copy (newer client_updated_at) replaces the form and bumps its version
    fixed = dict(bad, answers=base_answers(), client_updated_at=(datetime(2026, 10, 7, 13, 0, tzinfo=timezone.utc)).isoformat())
    r = client.post("/api/v1/mefm/sync/push", json={"device_id": me["device_id"], "visits": [fixed]}, headers=me["headers"]).json()
    assert r["applied"] == 1 and r["receipts"][0]["version"] == 1
    newer = dict(fixed, answers=base_answers(J10="Edited"), client_updated_at=(datetime(2026, 10, 7, 14, 0, tzinfo=timezone.utc)).isoformat())
    r = client.post("/api/v1/mefm/sync/push", json={"device_id": me["device_id"], "visits": [newer]}, headers=me["headers"]).json()
    assert r["receipts"][0]["version"] == 2
    # a form without a GPS fix never gets in
    r = client.post("/api/v1/mefm/sync/push", json={"device_id": me["device_id"], "visits": [{**visit(), "gps": None}]}, headers=me["headers"])
    assert r.status_code == 422

    # reads: the officer sees their own district's visits; the issues log holds the typed row and the automatic critical rows
    rows = client.get("/api/v1/mefm/visits", headers=me["headers"]).json()
    assert len(rows) == 3 and all(x["district"] == "Western Area Urban" for x in rows)
    detail = client.get(f"/api/v1/mefm/visits/{far['id']}", headers=me["headers"]).json()
    assert detail["ea_name"] == "Tower Hill A" and detail["chiefdom"] == "Central One" and detail["section"] == "Tower Hill" and detail["sa_code"] == "WAU-SA01"
    assert detail["distance_to_ea_m"] > 1000 and detail["critical_count"] == 2 and detail["open_issues"] == 3
    questions = sorted((i["question"], i["severity"], i["auto"]) for i in detail["issues"])
    assert questions == [("C5", "Critical", True), ("D4", "Major", False), ("G2", "Critical", True)]
    assert detail["indicators"]["tablet_ready"] is False and detail["overall_rating"] == 3
    # the tablet learns the state of its forms at the next pull
    pull = client.get("/api/v1/mefm/sync/pull", params={"device_id": me["device_id"]}, headers=me["headers"]).json()
    states = {v["id"]: v for v in pull["visits"]}
    assert states[far["id"]]["open_issues"] == 3 and states[far["id"]]["flags"] and states[fixed["id"]]["version"] == 2

    # district isolation: another district's officer sees nothing; the national M&E and the admin see everything
    war = me_device(client, admin, geo, "me.war", "WAR")
    assert client.get("/api/v1/mefm/visits", headers=war["headers"]).json() == []
    assert client.get(f"/api/v1/mefm/visits/{good['id']}", headers=war["headers"]).status_code == 404
    officer(client, admin, "me.hq", "ME")
    hq = auth(login(client, "me.hq", "Password123")["access_token"])
    assert len(client.get("/api/v1/mefm/visits", headers=hq).json()) == 3
    assert len(client.get("/api/v1/mefm/visits", params={"district_id": geo["districts"]["WAR"]["id"]}, headers=hq).json()) == 0
    form = client.get("/api/v1/mefm/form", headers=hq).json()
    assert form["version"] == pull["form_version"] and form["indicators"][0]["code"] == "team_in_ea"


def test_speed_and_repeated_point_flags(client, admin, geo):
    client.post("/api/v1/admin/reference/import", files={"file": ("frame.csv", FRAME_CSV, "text/csv")}, headers=admin)
    me = me_device(client, admin, geo)
    t0 = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)
    first = visit(at=t0.isoformat())
    same = visit(ea="5200100102", at=(t0 + timedelta(hours=1)).isoformat())  # identical coordinates one hour later
    fast = visit(ea="5200100102", lat=8.4849, lng=-13.9, at=(t0 + timedelta(hours=1, minutes=10)).isoformat())  # ~74 km in 10 minutes
    r = client.post("/api/v1/mefm/sync/push", json={"device_id": me["device_id"], "visits": [first, same, fast]}, headers=me["headers"]).json()
    rc = {x["id"]: x for x in r["receipts"]}
    assert rc[first["id"]]["flags"] == [] and rc[same["id"]]["flags"] == ["repeated_point"] and "too_fast" in rc[fast["id"]]["flags"]
