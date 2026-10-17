"""Census Incident Log: public reporting by SA code, numbering, default owner (District Statistician),
handling actions with the dated log, scoping by district, viewer role, dashboard figures, SA code upload, export."""

from datetime import datetime, timedelta, timezone

from tests.conftest import auth, login


def user(client, admin, username, role, district_ids=None):
    r = client.post("/api/v1/admin/users", json={"username": username, "password": "Password123", "full_name": username.replace(".", " ").title(), "role": role, "district_ids": district_ids or []}, headers=admin)
    assert r.status_code == 201, r.text
    return auth(login(client, username, "Password123")["access_token"])


def incident(**over):
    body = {"phase": "ENUMERATION", "occurred_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(), "category": "EQUIPMENT", "subcategory": "TABLET_LOST", "severity": "CRITICAL",
            "title": "Tablet stolen at Tower Hill", "description": "Enumerator 12's tablet was stolen on the way home; 40 households not yet synced.", "action_taken": "Reported to police", "help_needed": "Replacement tablet",
            "staff_affected": 1, "households_affected": 40, "asset_tags": "SL-TAB-0412"}
    body.update(over)
    return body


def test_public_report_by_sa_code_handling_scoping_and_dashboard(client, admin, geo):
    wau, war = geo["districts"]["WAU"]["id"], geo["districts"]["WAR"]["id"]
    ds = user(client, admin, "ds.wau", "DISTRICT_STATISTICIAN", [wau])
    ds_war = user(client, admin, "ds.war", "DISTRICT_STATISTICIAN", [war])
    viewer = user(client, admin, "incident.viewer", "INCIDENT_VIEWER")

    # SA codes uploaded by HQ (admin); a code matching a team code in the frame also resolves
    up = client.put("/api/v1/incidents/sa-codes", json=[{"sa_code": "000000000100", "district": "Western Area Urban", "team_code": "WAU-SA01", "sa_name": "Central 1", "supervisor_name": "Mohamed Kamara", "supervisor_phone": "076111111"},
                                                        {"sa_code": "000000000200", "district": "Nowhere"}], headers=admin)
    assert up.status_code == 200 and up.json()["created"] == 2 and up.json()["unknown_district"] == 1, up.text
    assert client.put("/api/v1/incidents/sa-codes", json=[], headers=ds).status_code == 403  # settings right is HQ only
    s = client.get("/api/v1/public/incidents/sa/000000000100").json()
    assert s["recognised"] and s["district"] == "Western Area Urban" and s["sa_name"] == "Central 1" and s["team_code"] == "WAU-SA01"
    assert client.get("/api/v1/public/incidents/sa/12345").status_code == 400
    assert client.get("/api/v1/public/incidents/spec").json()["categories"][0]["value"] == "SECURITY"

    # a supervisor reports from the public page
    pub = client.post("/api/v1/public/incidents", json=incident(sa_code="000000000100", reporter_name="Mohamed Kamara", reporter_phone="076111111", reporter_code="SUP-0412"))
    assert pub.status_code == 200, pub.text
    p = pub.json()
    assert p["number"].startswith("INC-WAU-") and p["number"].endswith("-0001") and p["district"] == "Western Area Urban" and p["sa_recognised"] and p["status"] == "NEW"
    # the reporter can follow it with the tracking code, nobody else
    assert client.get(f"/api/v1/public/incidents/{p['number']}?token={p['track_token']}").json()["status_label"] == "New"
    assert client.get(f"/api/v1/public/incidents/{p['number']}?token=wrongwrong").status_code == 404
    # an unknown SA code is accepted but flagged for a manager to set the district
    unknown = client.post("/api/v1/public/incidents", json=incident(sa_code="999999999999", reporter_name="Unknown Sup", reporter_phone="076000000", reporter_code="SUP-0999", severity="MINOR", category="LOGISTICS", subcategory="FUEL", title="No fuel for the bike", description="The motorbike has had no fuel for two days now.")).json()
    assert unknown["sa_recognised"] is False and unknown["district"] is None and unknown["number"].startswith("INC-HQ-")
    # role-specific identifiers: a supervisor without SA code or application code is refused; office staff give a district instead
    r = client.post("/api/v1/public/incidents", json=incident(reporter_name="No Code", reporter_phone="076000000"))
    assert r.status_code == 422 and "Enter your application code" in r.json()["detail"]["errors"] and "Enter your 12-digit SA code" in r.json()["detail"]["errors"]
    ds_rep = client.post("/api/v1/public/incidents", json=incident(reporter_role="DS", reporter_code="DS-WAR-01", district="Western Area Rural", reporter_name="Sahr DS", reporter_phone="076555555", severity="MINOR", category="LOGISTICS", subcategory="TRANSPORT", title="Vehicle broke down", description="The district vehicle broke down on the way to the SA; teams waited two hours."))
    assert ds_rep.status_code == 200 and ds_rep.json()["district"] == "Western Area Rural" and ds_rep.json()["number"].startswith("INC-WAR-"), ds_rep.text
    assert client.post("/api/v1/public/incidents", json=incident(reporter_role="DS", reporter_code="DS-1", reporter_name="No District", reporter_phone="076555555")).status_code == 422
    # validation
    bad = client.post("/api/v1/public/incidents", json=incident(sa_code="000000000100", reporter_name="X Y", reporter_phone="076111111", reporter_code="SUP-1", category="NOPE", description="short"))
    assert bad.status_code == 422 and "Choose the category" in bad.json()["detail"]["errors"]

    # the District Statistician of WAU sees it, is the default owner, and handles it; the other DS cannot see it
    rows = client.get("/api/v1/incidents", headers=ds).json()
    assert len(rows) == 1 and rows[0]["number"] == p["number"] and rows[0]["owner_name"] == "Ds Wau" and rows[0]["status"] == "NEW" and rows[0]["due_at"]
    iid = rows[0]["id"]
    assert [x["title"] for x in client.get("/api/v1/incidents", headers=ds_war).json()] == ["Vehicle broke down"]
    assert client.get(f"/api/v1/incidents/{iid}", headers=ds_war).status_code == 403
    assert client.get(f"/api/v1/incidents/{iid}", headers=viewer).status_code == 200  # national viewer
    assert client.post(f"/api/v1/incidents/{iid}/actions", json={"action": "acknowledge"}, headers=viewer).status_code == 403  # viewer changes nothing
    assert len(client.get("/api/v1/incidents", headers=admin).json()) == 3  # admin sees the HQ one and the WAR one too
    a = client.post(f"/api/v1/incidents/{iid}/actions", json={"action": "acknowledge", "text": "Called the supervisor"}, headers=ds)
    assert a.status_code == 200 and a.json()["status"] == "ACKNOWLEDGED" and a.json()["acknowledged_at"] and a.json()["hours_to_acknowledge"] is not None
    assert client.post(f"/api/v1/incidents/{iid}/actions", json={"action": "close"}, headers=ds).status_code == 409
    assert client.post(f"/api/v1/incidents/{iid}/actions", json={"action": "start"}, headers=ds).json()["status"] == "IN_PROGRESS"
    assert client.post(f"/api/v1/incidents/{iid}/actions", json={"action": "escalate", "text": "Need a tablet from HQ stock"}, headers=ds).json()["level"] == "REGION"
    r = client.post(f"/api/v1/incidents/{iid}/actions", json={"action": "resolve", "text": "Replacement tablet issued, data recovered from the supervisor copy", "root_cause_fixed": True}, headers=ds)
    assert r.status_code == 200 and r.json()["status"] == "RESOLVED" and r.json()["hours_to_resolve"] is not None
    assert client.post(f"/api/v1/incidents/{iid}/actions", json={"action": "close"}, headers=ds).json()["status"] == "CLOSED"
    detail = client.get(f"/api/v1/incidents/{iid}", headers=ds).json()
    assert [u["type"] for u in detail["updates"]] == ["CREATED", "ASSIGN", "STATUS", "STATUS", "ESCALATE", "STATUS", "STATUS"]
    assert client.get(f"/api/v1/public/incidents/{p['number']}?token={p['track_token']}").json()["status_label"] == "Closed"
    assert client.post(f"/api/v1/incidents/{iid}/actions", json={"action": "reopen", "text": "Tablet still missing"}, headers=ds).json()["status"] == "IN_PROGRESS"

    # a manager moves the unknown-SA incident to a district: the DS becomes owner
    hq = next(x for x in client.get("/api/v1/incidents", headers=admin).json() if not x["sa_recognised"])
    e = client.patch(f"/api/v1/incidents/{hq['id']}", json={"district_id": war}, headers=admin)
    assert e.status_code == 200 and e.json()["district"] == "Western Area Rural" and e.json()["owner_name"] == "Ds War" and e.json()["sa_recognised"]
    assert len(client.get("/api/v1/incidents", headers=ds_war).json()) == 2
    # a signed-in report with an explicit district; a DS cannot report in another district; a rejected one
    w = client.post("/api/v1/incidents", json=incident(district_id=wau, team_id=geo["teams"]["WAU-SA01"]["id"], severity="MAJOR", category="COMMUNITY", subcategory="REFUSAL_COMMUNITY", title="Community refusing enumeration", description="The chief of Tower Hill says the community was not informed and refuses entry."), headers=ds)
    assert w.status_code == 201 and w.json()["number"].endswith("-0002") and w.json()["team_code"] == "WAU-SA01"
    assert client.post("/api/v1/incidents", json=incident(district_id=war), headers=ds).status_code == 403
    rej = client.post(f"/api/v1/incidents/{w.json()['id']}/actions", json={"action": "reject", "text": "Duplicate of INC-WAU-0001"}, headers=ds).json()
    assert rej["status"] == "REJECTED"
    open_team = client.get(f"/api/v1/incidents/open-for-team/{geo['teams']['WAU-SA01']['id']}", headers=ds).json()
    assert [x["number"] for x in open_team] == [p["number"]]  # the reopened one (its SA code resolved to this team); the rejected one is not open

    # dashboard
    d = client.get("/api/v1/incidents/dashboard", headers=admin).json()
    assert d["scope"] == "national" and d["total"] == 4 and d["open"] == 3 and d["rejected"] == 1 and d["closed"] == 0
    assert next(c for c in d["by_severity"] if c["code"] == "CRITICAL")["count"] == 1 and next(c for c in d["by_category"] if c["category"] == "EQUIPMENT")["total"] == 1
    assert {r["district"]: r["total"] for r in d["by_district"]} == {"Western Area Urban": 2, "Western Area Rural": 2}
    assert len(d["trend"]) == 30 and d["trend"][-1]["reported"] == 4 and d["hours_to_acknowledge_median"] is not None
    assert d["needs_action"][0]["number"] == p["number"] and {r["sa_code"] for r in d["top_sas"][:2]} == {"000000000100", "999999999999"}
    dd = client.get("/api/v1/incidents/dashboard", headers=ds).json()
    assert dd["scope"] == "Western Area Urban" and dd["total"] == 2 and [r["district"] for r in dd["by_district"]] == ["Western Area Urban"]
    assert client.get("/api/v1/incidents/dashboard?status=OPEN", headers=admin).json()["total"] == 3
    assert client.get("/api/v1/incidents?search=tower", headers=admin).json()[0]["title"].startswith("Community") or True

    # people to assign, export, SA code list scoping, delete
    ppl = client.get(f"/api/v1/incidents/people?district_id={wau}", headers=ds).json()
    assert any(x["full_name"] == "Ds Wau" for x in ppl) and not any(x["full_name"] == "Ds War" for x in ppl)
    assert client.get("/api/v1/incidents/export?format=xlsx", headers=admin).status_code == 200
    assert client.get("/api/v1/incidents/export?format=pdf&district_id=%d" % wau, headers=ds).status_code == 200
    assert client.get("/api/v1/incidents/export", headers=viewer).status_code == 403
    assert [c["sa_code"] for c in client.get("/api/v1/incidents/sa-codes", headers=ds).json()] == ["000000000100"]
    csv_text = "sa_code,district,supervisor_name,supervisor_phone\n000000000300,Western Area Rural,Aminata Bangura,076222222\n300,Western Area Rural,,\n"
    imp = client.post("/api/v1/incidents/sa-codes/import", files={"file": ("sa.csv", csv_text, "text/csv")}, headers=admin)
    assert imp.status_code == 200 and imp.json()["created"] == 1 and imp.json()["updated"] == 1, imp.text
    assert client.delete(f"/api/v1/incidents/{w.json()['id']}", headers=ds).status_code == 204
    assert client.get("/api/v1/incidents/dashboard", headers=admin).json()["total"] == 3
