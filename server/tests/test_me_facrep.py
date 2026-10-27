"""Daily Facilitator's Report (ToT, in-person): the public form on a training's link, one report per hall per
day with corrections from the same device, the summary by venue, hall and day, exports and the me_fac rights."""

from datetime import date

from tests.conftest import auth, login


def user(client, admin, username, role):
    r = client.post("/api/v1/admin/users", json={"username": username, "password": "Password123", "full_name": username, "role": role}, headers=admin)
    assert r.status_code == 201, r.text
    return auth(login(client, username, "Password123")["access_token"])


def report(**over):
    body = {"report_date": date.today().isoformat(), "training_day": 2, "venue": "Bo", "hall": "Hall 1", "lead_facilitator": "Mohamed Kamara", "other_facilitators": "Fatmata Sesay, Ibrahim Conteh",
            "email": "lead.hall1@example.org", "registered": 40, "present": 36, "delivered": "PARTLY", "missed_sessions": ["Chapter 7 – Use of Maps, GIS and Enumeration Area Boundaries"], "minutes_lost": 45,
            "missed_reason": "Projector failed for 45 minutes in the afternoon", "r_knowledge": 4, "r_engagement": 4, "r_illustrations": 3, "r_connectivity": 2, "r_coordination": 4,
            "e_internet": 2, "e_internet_details": "Participants' hotspot dropped twice", "e_power": 4, "e_power_details": None, "e_devices": "3 tablets short", "e_devices_details": "Shared in pairs", "e_food": "Late lunch", "e_food_details": None,
            "went_right": "Practice on the map exercise worked well (D2.3)", "repeat_share": "Pair work on the GIS maps", "went_wrong": "Projector failure delayed chapter 7",
            "difficult_topics": ["Chapter 7 – Use of Maps, GIS and Enumeration Area Boundaries"], "difficult_notes": "Boundaries on the map", "recommendations": "Spare projector in each hall before tomorrow",
            "gaps": "Slide 14 has the old EA code format", "actors": ["COORD", "TECH"], "actor_other": None, "comments": None}
    body.update(over)
    return body


def test_public_report_summary_export_and_rights(client, admin):
    me = user(client, admin, "me.officer", "ME")
    dqm = user(client, admin, "dqm.wau", "NATIONAL_DQM")
    # the Training of Trainers entry ships with the server: its form link exists before anyone creates a training
    shipped = client.get("/api/v1/me/facreports/rounds", headers=me).json()
    tot = [x for x in shipped if x["round"]["phase"] == "TOT"]
    assert len(tot) == 1 and tot[0]["round"]["status"] == "OPEN" and tot[0]["round"]["agenda_days"] == 10 and tot[0]["reports"] == 0
    assert client.get(f"/api/v1/public/facreport/{tot[0]['round']['token']}").status_code == 200
    r = client.post("/api/v1/me/facilitators/rounds", json={"title": "ToT in-person, October 2026", "phase": "TOT", "period_start": "2026-10-26", "agenda_template": "TRAINING_2026"}, headers=me)
    assert r.status_code == 201, r.text
    rd = r.json()
    token = rd["token"]
    spec = client.get("/api/v1/me/facreports/form", headers=me).json()
    assert spec["venues"][0] == "Bo" and len(spec["ratings"]) == 5 and spec["actors"][-1]["value"] == "OTHER"
    assert client.get("/api/v1/me/facreports/form", headers=dqm).status_code == 403

    # the public page needs no sign-in and carries the chapters per day
    pub = client.get(f"/api/v1/public/facreport/{token}").json()
    assert pub["title"] == rd["title"] and pub["form"]["title"].startswith("Daily Facilitator") and any(a["day"] == 2 for a in pub["agenda"])
    assert client.get("/api/v1/public/facreport/not-a-token").status_code == 404

    # submit, correct from the same device, one report per hall per day
    s = client.post(f"/api/v1/public/facreport/{token}/submit", json=report())
    assert s.status_code == 200, s.text
    sent = s.json()
    assert sent["mean_rating"] == 3.4 and sent["attendance_pct"] == 90.0 and sent["edit_token"]
    dup = client.post(f"/api/v1/public/facreport/{token}/submit", json=report(lead_facilitator="Someone Else"))
    assert dup.status_code == 409 and "One report per hall per day" in dup.json()["detail"]
    fixed = client.post(f"/api/v1/public/facreport/{token}/submit", json={**report(present=38, r_connectivity=3), "report_id": sent["report_id"], "edit_token": sent["edit_token"]})
    assert fixed.status_code == 200 and fixed.json()["report_id"] == sent["report_id"] and fixed.json()["attendance_pct"] == 95.0
    assert client.post(f"/api/v1/public/facreport/{token}/submit", json={**report(), "report_id": sent["report_id"], "edit_token": "wrong"}).status_code == 403
    # validation: present > registered, partly without a reason, other actor without a name
    assert client.post(f"/api/v1/public/facreport/{token}/submit", json=report(hall="Hall 9", present=50)).status_code == 422
    assert client.post(f"/api/v1/public/facreport/{token}/submit", json=report(hall="Hall 9", missed_reason=None)).status_code == 422
    assert client.post(f"/api/v1/public/facreport/{token}/submit", json=report(hall="Hall 9", actors=["OTHER"])).status_code == 422
    # a second hall and a second venue
    assert client.post(f"/api/v1/public/facreport/{token}/submit", json=report(hall="Hall 2", lead_facilitator="Aminata Bangura", delivered="FULL", missed_reason=None, minutes_lost=None, r_knowledge=5, r_connectivity=5, e_internet=5, present=40)).status_code == 200
    assert client.post(f"/api/v1/public/facreport/{token}/submit", json=report(venue="Kenema", hall="Hall 1", training_day=3, lead_facilitator="Sahr Gbamanja", delivered="NO", missed_reason="Power cut all afternoon", r_engagement=2, present=20)).status_code == 200

    rounds = client.get("/api/v1/me/facreports/rounds", headers=me).json()
    row = next(x for x in rounds if x["round"]["id"] == rd["id"])
    assert row["reports"] == 3 and row["halls"] == 3 and row["venues"] == 2 and row["attention"] == 2

    sm = client.get(f"/api/v1/me/facreports/rounds/{rd['id']}/summary", headers=me).json()
    assert sm["reports"] == 3 and sm["registered"] == 120 and sm["present"] == 98 and sm["attendance_pct"] == 81.7
    assert [c["count"] for c in sm["delivered"]] == [1, 1, 1] and sm["minutes_lost"] == 90  # 45 in Bo Hall 1 + 45 in Kenema
    assert {g["label"] for g in sm["by_venue"]} == {"Bo", "Kenema"} and [g["key"] for g in sm["by_day"]] == ["2", "3"]
    assert sm["actors"][0]["count"] == 3 and sm["difficult_topics"][0]["count"] == 3
    assert len(sm["needs_attention"]) == 2 and any("not delivered" in reason for x in sm["needs_attention"] for reason in x["reasons"])
    bo = client.get(f"/api/v1/me/facreports/rounds/{rd['id']}/summary?venue=Bo", headers=me).json()
    assert bo["reports"] == 2 and bo["halls"] == 2

    rows = client.get(f"/api/v1/me/facreports/rounds/{rd['id']}/reports?hall=Hall%201", headers=me).json()
    assert len(rows) == 2 and all(x["hall"] == "Hall 1" for x in rows)
    first = next(x for x in rows if x["venue"] == "Bo")
    assert first["present"] == 38 and first["actor_labels"] == ["Training Coordinator", "Platform / technical support"]
    # the M&E team can edit and remove; a viewer cannot
    e = client.put(f"/api/v1/me/facreports/rounds/{rd['id']}/reports/{first['id']}", json=report(present=37, r_connectivity=3), headers=me)
    assert e.status_code == 200 and e.json()["present"] == 37 and e.json()["edited_by_name"] == "me.officer"
    assert client.delete(f"/api/v1/me/facreports/rounds/{rd['id']}/reports/{first['id']}", headers=dqm).status_code == 403
    for fmt, ctype in (("xlsx", "spreadsheetml"), ("pdf", "application/pdf")):
        x = client.get(f"/api/v1/me/facreports/rounds/{rd['id']}/export?format={fmt}", headers=me)
        assert x.status_code == 200 and ctype in x.headers["content-type"], fmt
    assert client.delete(f"/api/v1/me/facreports/rounds/{rd['id']}/reports/{first['id']}", headers=me).status_code == 204
    assert client.get(f"/api/v1/me/facreports/rounds/{rd['id']}/summary", headers=me).json()["reports"] == 2
    # a closed training takes no more reports
    client.patch(f"/api/v1/me/facilitators/rounds/{rd['id']}", json={"status": "CLOSED"}, headers=me)
    assert client.post(f"/api/v1/public/facreport/{token}/submit", json=report(hall="Hall 3")).status_code == 409
