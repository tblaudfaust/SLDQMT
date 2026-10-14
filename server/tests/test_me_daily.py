"""Daily Evaluation: rounds shared by link, the lead trainer's daily class report with its rules,
the summary with every detail, the export, and access limited to the me_daily rights."""

from datetime import date, timedelta

from tests.conftest import auth, login


def me_user(client, admin, username="me.officer", role="ME"):
    r = client.post("/api/v1/admin/users", json={"username": username, "password": "Password123", "full_name": username, "role": role}, headers=admin)
    assert r.status_code == 201, r.text
    return auth(login(client, username, "Password123")["access_token"])


def report(**over):
    body = {
        "report_date": date.today().isoformat(), "training_day": 1, "class_hall": "Hall 2", "venue": "Bo Teachers College", "lead_trainer": "Fatmata Koroma", "phase": "FIELD", "district": "Bo",
        "expected": 40, "present": 36, "late": 4, "coverage": "SOME", "incomplete_topic": "Household listing practical, time ran out", "practice_minutes": 90, "practice_not_scheduled": False,
        "checks": ["QUIZ", "PRACTICAL"], "task_checked": "Household roster on CAPI", "number_checked": 36, "number_met": 29, "criterion": "8 of 10 quiz items and a complete roster",
        "learning_gap": "Relationship to head codes confused", "followup_count": 7, "followup_not_assessed": False,
        "delivery_content": "GOOD", "delivery_participation": "SOME", "delivery_time": "MAJOR", "support": ["DEVICES", "INTERNET_POWER"], "support_other": None,
        "actions": [{"issue": "6 tablets not charged, 30 minutes lost", "action": "Charge overnight at the college office", "owner_due": "Logistics, tonight"}],
        "mgmt_help": True, "raised_to": "District coordinator",
    }
    body.update(over)
    return body


def test_rounds_reports_summary_export_and_access(client, admin):
    me = me_user(client, admin)
    # a plain M&E officer created with the ME role has the daily rights; a district DQM does not
    r = client.post("/api/v1/me/daily/rounds", json={"title": "Field staff training, Southern region", "phase": "FIELD", "period_start": "2026-10-12", "period_end": "2026-10-23", "description": "Send one form per class each day."}, headers=me)
    assert r.status_code == 201, r.text
    rd = r.json()
    assert rd["status"] == "OPEN" and rd["reports"] == 0 and rd["token"]
    token = rd["token"]
    assert client.post("/api/v1/me/daily/rounds", json={"title": "field staff training, southern region", "phase": "FIELD"}, headers=me).status_code == 409
    dqm = me_user(client, admin, "dqm.bo", "DISTRICT_DQM")
    assert client.get("/api/v1/me/daily/rounds", headers=dqm).status_code == 403

    # public page and submissions
    pub = client.get(f"/api/v1/public/daily/{token}")
    assert pub.status_code == 200 and pub.json()["form"]["phases"][2]["value"] == "FIELD" and pub.json()["status"] == "OPEN"
    assert client.get("/api/v1/public/daily/not-a-token").status_code == 404
    bad = client.post(f"/api/v1/public/daily/{token}/submit", json=report(present=50, number_met=40, coverage="ALL", support=["NONE", "OTHER"], actions=[{"issue": "a", "action": ""}, {"issue": "b", "action": "c"}, {"issue": "d", "action": "e"}]))
    assert bad.status_code == 422, bad.text
    errs = bad.json()["detail"]["errors"]
    assert "Present cannot exceed the expected trainees" in errs and "The number meeting the criterion cannot exceed the number checked" in errs
    assert "None cannot be combined with a support problem" in errs and "Record at most 2 priority actions" in errs
    assert client.post(f"/api/v1/public/daily/{token}/submit", json=report(report_date=(date.today() + timedelta(days=1)).isoformat())).status_code == 400
    ok = client.post(f"/api/v1/public/daily/{token}/submit", json=report())
    assert ok.status_code == 200, ok.text
    first = ok.json()
    # the same browser corrects its report; another device cannot
    fixed = client.post(f"/api/v1/public/daily/{token}/submit", json={**report(present=37), "report_id": first["report_id"], "edit_token": first["edit_token"]})
    assert fixed.status_code == 200 and fixed.json()["report_id"] == first["report_id"]
    assert client.post(f"/api/v1/public/daily/{token}/submit", json={**report(), "report_id": first["report_id"], "edit_token": "wrong"}).status_code == 403
    client.post(f"/api/v1/public/daily/{token}/submit", json=report(class_hall="Hall 3", lead_trainer="Mohamed Sesay", expected=38, present=38, late=0, coverage="ALL", incomplete_topic=None, checks=["NOT_ASSESSED"], number_checked=None, number_met=None, task_checked=None, criterion=None, learning_gap="None", followup_count=None, followup_not_assessed=True, delivery_content="GOOD", delivery_participation="GOOD", delivery_time="GOOD", support=["NONE"], actions=[], mgmt_help=False, raised_to=None))
    client.post(f"/api/v1/public/daily/{token}/submit", json=report(training_day=2, report_date=date.today().isoformat(), present=35, late=1, district="Bonthe", practice_minutes=None, practice_not_scheduled=True))

    # summary: every detail
    s = client.get(f"/api/v1/me/daily/rounds/{rd['id']}/summary", headers=me).json()
    assert s["reports"] == 3 and s["classes"] == 2 and s["days"] == 2 and s["trainers"] == 2 and s["districts"] == 2
    assert s["expected"] == 118 and s["present"] == 110 and s["attendance_rate"] == 93.2 and s["late"] == 5
    assert [c["count"] for c in s["coverage"]] == [1, 2, 0] and s["agenda_all_pct"] == 33.3
    assert s["practice_minutes_avg"] == 90.0 and s["practice_not_scheduled"] == 1
    assert s["assessed"] == 2 and s["checked"] == 72 and s["met"] == 58 and s["pass_rate"] == 80.6 and s["followup"] == 14 and s["followup_not_assessed"] == 1
    assert [c["count"] for c in s["delivery"]["time"]] == [1, 0, 2] and s["reports_with_major_gaps"] == 2
    assert next(c for c in s["support"] if c["code"] == "DEVICES")["count"] == 2 and s["help_requests"] == 2 and s["actions_total"] == 2
    assert [g["label"] for g in s["by_day"]] == ["Day 1", "Day 2"] and s["by_day"][0]["reports"] == 2 and s["by_day"][0]["attendance_rate"] == 96.2
    assert {g["label"] for g in s["by_class"]} == {"Hall 2", "Hall 3"} and {g["label"] for g in s["by_district"]} == {"Bo", "Bonthe"}
    assert len(s["incomplete_topics"]) == 2 and len(s["learning_gaps"]) == 2 and len(s["help_requested"]) == 2 and s["actions"][0]["owner_due"] == "Logistics, tonight"
    assert s["latest"][0]["pass_rate"] == 80.6 and s["latest"][0]["major_gaps"] == 1 and s["round"]["reports"] == 3
    # filters narrow every figure
    f = client.get(f"/api/v1/me/daily/rounds/{rd['id']}/summary?district=Bonthe", headers=me).json()
    assert f["reports"] == 1 and f["filters"]["district"] == "Bonthe"
    assert client.get(f"/api/v1/me/daily/rounds/{rd['id']}/summary?class_hall=hall%203", headers=me).json()["reports"] == 1

    # reports list, manager edit and delete, export
    rows = client.get(f"/api/v1/me/daily/rounds/{rd['id']}/reports", headers=me).json()
    assert len(rows) == 3 and rows[0]["checks_label"] and "phase_label" in rows[0]
    rid = first["report_id"]
    e = client.put(f"/api/v1/me/daily/rounds/{rd['id']}/reports/{rid}", json=report(present=30), headers=me)
    assert e.status_code == 200 and e.json()["present"] == 30 and e.json()["edited_by_name"] == "me.officer"
    assert client.get(f"/api/v1/me/daily/rounds/{rd['id']}/reports/{rid}", headers=dqm).status_code == 403
    x = client.get(f"/api/v1/me/daily/rounds/{rd['id']}/export?format=xlsx", headers=me)
    assert x.status_code == 200 and x.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert client.get(f"/api/v1/me/daily/rounds/{rd['id']}/export?format=pdf&district=Bo", headers=me).status_code == 200
    assert client.delete(f"/api/v1/me/daily/rounds/{rd['id']}/reports/{rid}", headers=me).status_code == 204
    assert client.get(f"/api/v1/me/daily/rounds/{rd['id']}/summary", headers=me).json()["reports"] == 2
    # a round with reports cannot be deleted; closing stops submissions
    assert client.delete(f"/api/v1/me/daily/rounds/{rd['id']}", headers=me).status_code == 409
    assert client.patch(f"/api/v1/me/daily/rounds/{rd['id']}", json={"status": "CLOSED"}, headers=me).status_code == 200
    assert client.post(f"/api/v1/public/daily/{token}/submit", json=report()).status_code == 409
    # a right granted to another account opens the module to it
    uid = next(u["id"] for u in client.get("/api/v1/admin/users", headers=admin).json() if u["username"] == "dqm.bo")
    g = client.put(f"/api/v1/admin/users/{uid}/permissions", json={"grant": ["me_daily.view"], "revoke": []}, headers=admin)
    if g.status_code == 200:
        dqm2 = auth(login(client, "dqm.bo", "Password123")["access_token"])
        assert client.get("/api/v1/me/daily/rounds", headers=dqm2).status_code == 200


def test_daily_evaluation_admin_role(client, admin):
    """The Daily Evaluation Admin role sees the daily module only: no training evaluations, no field monitoring, no dashboard."""
    assert client.post("/api/v1/admin/users", json={"username": "daily.admin", "password": "Password123", "full_name": "Daily Admin", "role": "ME_DAILY"}, headers=admin).status_code == 201
    d = login(client, "daily.admin", "Password123")
    perms = set(d["user"]["permissions"])
    assert {"me_daily.view", "me_daily.manage"} <= perms and not {"me.view", "mefm.view", "dashboard.view"} & perms
    h = auth(d["access_token"])
    r = client.post("/api/v1/me/daily/rounds", json={"title": "Master training, Freetown", "phase": "MASTER"}, headers=h)
    assert r.status_code == 201
    assert client.get("/api/v1/me/daily/rounds", headers=h).status_code == 200
    assert client.get("/api/v1/me/evaluations", headers=h).status_code == 403
    assert client.get("/api/v1/mefm/overview", headers=h).status_code == 403
    assert client.get("/api/v1/admin/users", headers=h).status_code == 403
