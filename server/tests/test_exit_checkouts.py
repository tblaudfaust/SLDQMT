from datetime import date, timedelta

from tests.test_dqm_reports import users  # noqa: F401  (fixture re-use)


def checkout_body(**over):
    body = {
        "staff_name": "Fatmata Sesay",
        "login_id": "006011",
        "role": "ENUMERATOR",
        "sa_ea_codes": "WAU-SA01 / WAU-SA01-EA01",
        "checklist": [{"n": n, "answer": "NO" if n in (3, 9) else "YES", "remarks": "Pending" if n == 9 else ""} for n in range(1, 13)],
        "enumerator_conduct": "Diligent",
        "items": [
            {"item": "TABLET", "returned": True, "condition": "Good", "clearance": ""},
            {"item": "SD_CARD", "returned": False, "condition": "Lost", "clearance": "Deduct"},
        ],
        "approvals": [{"role": "DISTRICT_FC", "name": "A. Koroma", "comment": "", "signed_on": date.today().isoformat()}],
    }
    body.update(over)
    return body


def test_workflow_district_submit_national_sign_clearance(client, users):  # noqa: F811
    r = client.post("/api/v1/exit-checkouts", json=checkout_body(), headers=users["wau"])
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["district_id"] == users["wau_id"] and c["status"] == "DRAFT" and len(c["checklist"]) == 12
    # Other district refused
    assert client.post("/api/v1/exit-checkouts", json=checkout_body(district_id=users["war_id"]), headers=users["wau"]).status_code == 403
    # Incomplete checklist cannot be submitted
    r2 = client.post("/api/v1/exit-checkouts", json=checkout_body(staff_name="Half Done", checklist=[{"n": 1, "answer": "YES", "remarks": ""}]), headers=users["wau"]).json()
    assert client.post(f"/api/v1/exit-checkouts/{r2['id']}/submit", headers=users["wau"]).status_code == 400

    r = client.post(f"/api/v1/exit-checkouts/{c['id']}/submit", headers=users["wau"])
    assert r.status_code == 200 and r.json()["status"] == "SUBMITTED"
    assert any(a["role"] == "DISTRICT_DQM" and a["name"] == "District DQM WAU" for a in r.json()["approvals"])

    assert client.post(f"/api/v1/exit-checkouts/{c['id']}/national-sign", json={"comment": "ok"}, headers=users["regional"]).status_code == 403
    r = client.post(f"/api/v1/exit-checkouts/{c['id']}/national-sign", json={"comment": "Countersigned"}, headers=users["national"])
    assert r.status_code == 200 and r.json()["status"] == "NATIONAL_SIGNED" and r.json()["national_signed_name"] == "National DQM"
    # District can no longer edit after countersign
    assert client.put(f"/api/v1/exit-checkouts/{c['id']}", json=checkout_body(), headers=users["wau"]).status_code == 409

    assert client.post(f"/api/v1/exit-checkouts/{c['id']}/clearance", json={"decision": "NOT_CLEARED"}, headers=users["national"]).status_code == 400
    r = client.post(f"/api/v1/exit-checkouts/{c['id']}/clearance", json={"decision": "CONDITIONAL", "outstanding_issues": "Replace SD card", "deadline": (date.today() - timedelta(days=1)).isoformat()}, headers=users["national"])
    assert r.status_code == 200 and r.json()["status"] == "CLEARED" and r.json()["decision"] == "CONDITIONAL"
    assert client.put(f"/api/v1/exit-checkouts/{c['id']}", json=checkout_body(), headers=users["national"]).status_code == 409

    for fmt in ("pdf", "xlsx"):
        assert client.get(f"/api/v1/exit-checkouts/{c['id']}/export", params={"format": fmt}, headers=users["regional"]).status_code == 200


def test_listing_and_summaries(client, users):  # noqa: F811
    a = client.post("/api/v1/exit-checkouts", json=checkout_body(), headers=users["wau"]).json()
    client.post("/api/v1/exit-checkouts", json=checkout_body(staff_name="Mohamed Kamara", role="SUPERVISOR", login_id="1961"), headers=users["wau"])
    client.post("/api/v1/exit-checkouts", json=checkout_body(staff_name="Sorie Koroma"), headers=users["war"])
    client.post(f"/api/v1/exit-checkouts/{a['id']}/submit", headers=users["wau"])
    client.post(f"/api/v1/exit-checkouts/{a['id']}/national-sign", json={}, headers=users["national"])
    client.post(f"/api/v1/exit-checkouts/{a['id']}/clearance", json={"decision": "CLEARED_PAYMENT"}, headers=users["national"])

    assert len(client.get("/api/v1/exit-checkouts", headers=users["wau"]).json()) == 2
    assert len(client.get("/api/v1/exit-checkouts", headers=users["regional"]).json()) == 3
    rows = client.get("/api/v1/exit-checkouts", params={"role": "SUPERVISOR"}, headers=users["national"]).json()
    assert len(rows) == 1 and rows[0]["checklist_no"] == 2 and rows[0]["items_missing"] == 1
    assert len(client.get("/api/v1/exit-checkouts", params={"search": "sorie"}, headers=users["national"]).json()) == 1

    d = client.get("/api/v1/exit-checkouts/summary", params={"level": "district"}, headers=users["wau"]).json()
    assert d["title"] == "Western Area Urban" and d["totals"]["total"] == 2 and d["totals"]["supervisors"] == 1
    assert d["totals"]["cleared"] == 1 and d["totals"]["cleared_payment"] == 1 and d["totals"]["draft"] == 1
    assert d["totals"]["checklist_no"][2] == 2 and d["totals"]["checklist_no"][8] == 2 and d["totals"]["items_missing"][5] == 2
    assert d["expected_staff"] == 3  # 1 supervisor + 2 enumerators in the WAU roster

    g = client.get("/api/v1/exit-checkouts/summary", params={"level": "region"}, headers=users["regional"]).json()
    assert {r["label"]: r["total"] for r in g["rows"]} == {"Western Area Urban": 2, "Western Area Rural": 1}
    assert g["totals"]["total"] == 3 and g["expected_staff"] == 5

    assert client.get("/api/v1/exit-checkouts/summary", params={"level": "national"}, headers=users["regional"]).status_code == 403
    n = client.get("/api/v1/exit-checkouts/summary", params={"level": "national"}, headers=users["national"]).json()
    assert n["unit_label"] == "Region" and n["rows"][0]["label"] == "Western" and n["rows"][0]["total"] == 3
    assert [x["label"] for x in n["districts"]] == ["Western Area Rural", "Western Area Urban"]
    for fmt in ("pdf", "xlsx"):
        assert client.get("/api/v1/exit-checkouts/summary/export", params={"level": "national", "format": fmt}, headers=users["national"]).status_code == 200
