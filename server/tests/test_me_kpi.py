"""M&E Field Tool (KPIs): the form spec, the geography bundle scoped by district, offline sync by client_id
(create, re-send, correct), validation, district scoping for the District M&E Officer, the summary with its
attention list, exports and the rights of the M&E roles."""

import uuid
from datetime import date, timedelta

from tests.conftest import auth, login


def user(client, admin, username, role, district_ids=None):
    r = client.post("/api/v1/admin/users", json={"username": username, "password": "Password123", "full_name": username, "role": role, "district_ids": district_ids or []}, headers=admin)
    assert r.status_code == 201, r.text
    return auth(login(client, username, "Password123")["access_token"])


def report(district_id, team_id=None, **over):
    body = {
        "client_id": str(uuid.uuid4()), "phase": "E", "report_date": date.today().isoformat(), "week": 2, "district_id": district_id, "chiefdom": "Central", "section": "Tower Hill", "team_id": team_id,
        "respondent_name": "Mohamed Kamara", "respondent_role": "SUPERVISOR", "eas_urban": 8, "eas_rural": 2, "enumerators": 10, "capi_version": "2.3.1",
        "answers": {
            "k1_1": "1", "k1_2": ["radio", "leaders"], "k1_3": "2", "k1_3_detail": "Nomadic groups", "k1_4": "Tax rumour", "k1_5": "1", "k1_5_detail": "Chief",
            "k2_1": "2", "k2_2": "1", "k2_3": "1", "k2_4": "2", "k2_5": "1",
            "k3_1": {"expected": 1200, "done": 480}, "k3_3": {"done": 3, "assigned": 10}, "k3_4": "1", "k3_4_detail": "2 refusals, chief called", "k3_5": "2", "k3_6": "2",
            "k4_1": {"working": 9, "issued": 10}, "k4_2": "2", "k4_3": "1", "k4_4": "1",
            "k5_1": {"urban": 60, "rural": 15}, "k5_2": "1", "k5_3": "Rain in the afternoon",
            "k6_1": {"completed": 480, "synced": 450}, "k6_2": ["connectivity"], "k6_3": "1",
            "k7_1": {"reviewed": 200, "errors": 6}, "k7_3": ["missing", "age"], "k7_4": "1", "k7_4_detail": "FC",
            "k8_1": {"selected": 20, "done": 18}, "k8_2": 2, "k8_3": "2",
            "k9_1": "1", "k9_2": "2", "k9_3": "1", "k9_3_detail": "2", "k9_4": "2", "k9_5": 3, "k9_6": "2",
            "k10_1": "1", "k10_2": "1", "k10_3": "1", "k10_4": "2", "k11_1": "Strong supervisor", "k11_6": ["connectivity", "electricity"],
            "b1": "3", "b3": "2",
        },
    }
    body.update(over)
    return body


def test_form_geo_sync_scoping_summary_export_and_rights(client, admin, geo):
    wau, war = geo["districts"]["WAU"]["id"], geo["districts"]["WAR"]["id"]
    team = geo["teams"]["WAU-SA01"]["id"]
    me = user(client, admin, "me.national", "ME")
    dist = user(client, admin, "me.wau", "ME_DISTRICT", [wau])
    dqm = user(client, admin, "dqm.national", "NATIONAL_DQM")

    spec = client.get("/api/v1/me/kpi/form", headers=dist).json()
    assert spec["version"] == 3 and [s["code"] for s in spec["sections"]][:3] == ["K1", "K2", "K3"] and len(spec["sections"]) == 12
    assert client.get("/api/v1/me/kpi/form", headers=dqm).status_code == 403

    # the geography bundle follows the officer's scope
    g = client.get("/api/v1/me/kpi/geo", headers=dist).json()
    assert [d["code"] for d in g["districts"]] == ["WAU"] and [t["code"] for t in g["teams"]] == ["WAU-SA01"] and g["teams"][0]["eas"] == 2 and g["teams"][0]["enumerators"] == 2 and g["teams"][0]["supervisor"] == "Mohamed Kamara"
    assert len(client.get("/api/v1/me/kpi/geo", headers=me).json()["districts"]) == 2

    # sync: create, re-send (idempotent), correct; outside the district refused; validation
    first = report(wau, team)
    s = client.post("/api/v1/me/kpi/sync", json={"reports": [first]}, headers=dist)
    assert s.status_code == 200, s.text
    assert s.json()["created"] == 1 and s.json()["results"][0]["status"] == "created"
    rid = s.json()["results"][0]["id"]
    again = client.post("/api/v1/me/kpi/sync", json={"reports": [first]}, headers=dist).json()
    assert again["updated"] == 1 and again["results"][0]["id"] == rid
    corrected = dict(first); corrected["answers"] = {**first["answers"], "k6_1": {"completed": 480, "synced": 480}}
    assert client.post("/api/v1/me/kpi/sync", json={"reports": [corrected]}, headers=dist).json()["updated"] == 1
    out = client.post("/api/v1/me/kpi/sync", json={"reports": [report(war), report(wau, team, answers={"k3_1": {"expected": 10, "done": 5}, "b1": "9"}), report(wau, team, report_date=(date.today() + timedelta(days=1)).isoformat())]}, headers=dist).json()
    assert out["errors"] == 3 and "outside your area" in out["results"][0]["message"] and "not one of the options" in out["results"][1]["message"] and "future" in out["results"][2]["message"]
    # a listing / enumeration report needs an SA; field practice does not
    assert client.post("/api/v1/me/kpi/sync", json={"reports": [report(wau, None)]}, headers=dist).json()["results"][0]["status"] == "error"
    mt = report(wau, None, phase="MT", practice_team="Hall 2 team A", week=None, answers={"k1_1": "1", "k2_1": "1", "k4_1": {"working": 5, "issued": 5}, "b1": "4"})
    assert client.post("/api/v1/me/kpi/sync", json={"reports": [mt]}, headers=dist).json()["created"] == 1

    # the national officer adds a report in the other district; the district officer never sees it
    other = report(war, geo["teams"]["WAR-SA01"]["id"], answers={**report(war)["answers"], "k3_1": {"expected": 1000, "done": 100}, "k6_1": {"completed": 100, "synced": 50}, "k11_4": "Threats at the market", "k5_2": "3", "b1": "2", "b2": "Need police escort"})
    assert client.post("/api/v1/me/kpi/sync", json={"reports": [other]}, headers=me).json()["created"] == 1
    assert len(client.get("/api/v1/me/kpi/reports", headers=dist).json()) == 2
    assert len(client.get("/api/v1/me/kpi/reports", headers=me).json()) == 3
    x = client.get(f"/api/v1/me/kpi/reports/{rid}", headers=dist).json()
    assert x["metrics"]["coverage_pct"] == 40.0 and x["metrics"]["synced_pct"] == 100.0 and x["metrics"]["error_pct"] == 3.0 and x["metrics"]["tablets_pct"] == 90.0 and x["sa_code"] == "WAU-SA01" and x["district"] == "Western Area Urban" and x["officer"] == "me.wau"

    # summary: national sees all three, with the attention list; the district officer sees Western Area Urban only
    sm = client.get("/api/v1/me/kpi/summary", headers=me).json()
    assert sm["scope"] == "national" and sm["reports"] == 3 and sm["districts"] == 2 and sm["safety_concerns"] == 1 and sm["escalations"] == 1
    assert sm["coverage_pct"] == 25.0 and sm["synced_pct"] == 75.0 and sm["informed_pct"] == 100.0 and sm["on_schedule_pct"] == 50.0
    assert [g["label"] for g in sm["by_phase"]] == ["Master trainers' field practice", "Census enumeration"]
    att = sm["attention"]
    assert len(att) == 1 and att[0]["district"] == "Western Area Rural" and "Safety / security concern" in att[0]["reasons"] and "Escalation requested" in att[0]["reasons"] and "Only 50.0% synced" in att[0]["reasons"] and "Behind by 3 days or more" in att[0]["reasons"]
    assert sm["blockers"][0]["label"] == "Connectivity" and sm["blockers"][0]["count"] == 2
    ds = client.get("/api/v1/me/kpi/summary", headers=dist).json()
    assert ds["scope"] == "Western Area Urban" and ds["reports"] == 2 and ds["attention"] == []
    assert client.get("/api/v1/me/kpi/summary?phase=MT", headers=me).json()["reports"] == 1
    assert client.get(f"/api/v1/me/kpi/summary?district_id={war}", headers=me).json()["reports"] == 1
    assert client.get("/api/v1/me/kpi/reports?mine=true", headers=me).json()[0]["district"] == "Western Area Rural"

    # rights: the district officer collects and views but cannot edit others' reports or export; the national officer can
    assert client.get("/api/v1/me/kpi/export?format=xlsx", headers=dist).status_code == 403
    assert client.put(f"/api/v1/me/kpi/reports/{rid}", json=first, headers=dist).status_code == 403
    x2 = client.put(f"/api/v1/me/kpi/reports/{rid}", json={**first, "answers": {**first["answers"], "b1": "4"}}, headers=me)
    assert x2.status_code == 200 and x2.json()["metrics"]["overall"] == 4 and x2.json()["edited_by_name"] == "me.national"
    e = client.get("/api/v1/me/kpi/export?format=xlsx", headers=me)
    assert e.status_code == 200 and e.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert client.get(f"/api/v1/me/kpi/export?format=pdf&district_id={wau}", headers=me).status_code == 200
    assert client.delete(f"/api/v1/me/kpi/reports/{rid}", headers=me).status_code == 204
    assert client.get("/api/v1/me/kpi/summary", headers=me).json()["reports"] == 2


def test_regional_officer_scope(client, admin, geo):
    wau = geo["districts"]["WAU"]["id"]
    r = client.post("/api/v1/admin/users", json={"username": "me.west", "password": "Password123", "full_name": "me.west", "role": "ME_REGIONAL", "region_ids": [geo["districts"]["WAU"]["region_id"]]}, headers=admin)
    assert r.status_code == 201, r.text
    reg = auth(login(client, "me.west", "Password123")["access_token"])
    g = client.get("/api/v1/me/kpi/geo", headers=reg).json()
    assert {d["code"] for d in g["districts"]} == {"WAU", "WAR"}
    assert client.post("/api/v1/me/kpi/sync", json={"reports": [report(wau, geo["teams"]["WAU-SA01"]["id"])]}, headers=reg).json()["created"] == 1
    assert client.get("/api/v1/me/kpi/export", headers=reg).status_code == 200
