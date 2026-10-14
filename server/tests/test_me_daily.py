"""Daily Evaluation: rounds with an agenda shared by link, the Daily Facilitator Report with its rules
(sessions with planned/actual times and computed minutes, evidence for scores 1, 2 and 5, logs),
the summary with every indicator, exports, escalation follow-up and access by the me_daily rights."""

from datetime import date, timedelta

from tests.conftest import auth, login


def me_user(client, admin, username="me.officer", role="ME"):
    r = client.post("/api/v1/admin/users", json={"username": username, "password": "Password123", "full_name": username, "role": role}, headers=admin)
    assert r.status_code == 201, r.text
    return auth(login(client, username, "Password123")["access_token"])


AGENDA = [
    {"day": 1, "topic": "Census concepts and reference night", "planned_start": "09:00", "planned_end": "10:30"},
    {"day": 1, "topic": "Household listing on CAPI", "planned_start": "11:00", "planned_end": "13:00"},
    {"day": 2, "topic": "Household questionnaire: roster and demographics", "planned_start": "09:00", "planned_end": "12:00"},
]


def report(**over):
    body = {
        "phase": "FIELD", "platform_venue": "Bo Teachers College, Hall 2", "class_hall": "Hall 2", "training_day": 1, "report_date": date.today().isoformat(),
        "lead_facilitator": "Fatmata Koroma", "co_facilitators": "Ibrahim Conteh", "district": "Bo",
        "sessions": [
            {"topic": "Census concepts and reference night", "planned_start": "09:00", "planned_end": "10:30", "actual_start": "09:15", "actual_end": "10:50", "delivered": "Y", "reason": ""},
            {"topic": "Household listing on CAPI", "planned_start": "11:00", "planned_end": "13:00", "actual_start": "11:10", "actual_end": "12:40", "delivered": "P", "reason": "Tablets not charged; practical cut short"},
        ],
        "carried_over": ["Household listing on CAPI"],
        "quiz_administered": True, "quiz_title": "Day 1 quiz", "mean_score": 72.5, "pass_rate": 81, "quiz_comments": None,
        "practice_minutes": 60, "practice_comments": None, "hardest_topics": ["Household listing on CAPI"], "hardest_comments": "Structure numbering confused",
        "q_content": 4, "q_content_evidence": None, "q_engagement": 5, "q_engagement_evidence": "All 36 trainees did the listing walk; 12 questions asked", "q_time": 2, "q_time_evidence": "Session 1 started 15 min late, practical lost 30 min",
        "q_illustrations": 4, "q_illustrations_evidence": None,
        "material_issues": [{"item": "Enumerator manual ch. 4, p. 31", "type": "ERROR", "severity": "H", "correction": "Replace the household definition with the reference-night rule"}],
        "g_internet": 3, "g_internet_details": "Slow after 11:00", "g_power": 2, "g_power_details": "Generator out 11:00 to 11:40; tablets ran on battery", "g_devices": 6, "g_devices_details": "6 trainees shared tablets", "g_food": 4, "g_food_details": None,
        "escalations": [{"issue": "6 tablets short in Hall 2", "raised_to": "District coordinator", "owner": "Logistics", "needed_by": "tomorrow 08:00", "status": "OPEN"}],
    }
    body.update(over)
    return body


def test_rounds_agenda_reports_summary_export_and_access(client, admin):
    me = me_user(client, admin)
    r = client.post("/api/v1/me/daily/rounds", json={"title": "Field staff training, Southern region", "phase": "FIELD", "period_start": "2026-10-12", "period_end": "2026-10-23"}, headers=me)
    assert r.status_code == 201, r.text
    rd = r.json()
    token = rd["token"]
    assert client.post("/api/v1/me/daily/rounds", json={"title": "field staff training, southern region", "phase": "FIELD"}, headers=me).status_code == 409
    dqm = me_user(client, admin, "dqm.bo", "DISTRICT_DQM")
    assert client.get("/api/v1/me/daily/rounds", headers=dqm).status_code == 403

    # agenda: the drop-down of topics on the form
    a = client.put(f"/api/v1/me/daily/rounds/{rd['id']}/agenda", json=AGENDA, headers=me)
    assert a.status_code == 200 and len(a.json()) == 3 and a.json()[1]["position"] == 2, a.text
    assert client.put(f"/api/v1/me/daily/rounds/{rd['id']}/agenda", json=[{"day": 1, "topic": "x", "planned_start": "10:00", "planned_end": "09:00"}], headers=me).status_code == 400
    pub = client.get(f"/api/v1/public/daily/{token}")
    assert pub.status_code == 200 and len(pub.json()["agenda"]) == 3 and pub.json()["form"]["evidence_scores"] == [1, 2, 5]
    assert client.get("/api/v1/public/daily/not-a-token").status_code == 404

    # rules
    bad = client.post(f"/api/v1/public/daily/{token}/submit", json=report(sessions=[{"topic": "Census concepts", "planned_start": "09:00", "planned_end": "08:00", "delivered": "N", "reason": ""}], q_time=1, q_time_evidence="", quiz_title="", g_devices=None,
                                                                            material_issues=[{"item": "", "type": None, "severity": "X", "correction": ""}], escalations=[{"issue": "", "raised_to": "CCIT", "status": "OPEN"}]))
    assert bad.status_code == 422, bad.text
    errs = bad.json()["detail"]["errors"]
    assert "Session 1: planned end must be after planned start" in errs and "Session 1: give the reason when a session is partly or not delivered" in errs
    assert "D: give the quiz / assessment title" in errs and any("evidence / justification is required for a score of 1" in x for x in errs)
    assert "G: give the number of devices short (0 if none)" in errs and "F issue 1: give the item (manual chapter, quiz, questionnaire ref.)" in errs
    assert "H escalation 1: describe the issue requiring management / CCIT action" in errs
    assert client.post(f"/api/v1/public/daily/{token}/submit", json=report(report_date=(date.today() + timedelta(days=1)).isoformat())).status_code == 400

    # a good report: minutes over/under computed, overall = mean of the four
    ok = client.post(f"/api/v1/public/daily/{token}/submit", json=report())
    assert ok.status_code == 200, ok.text
    first = ok.json()
    assert first["overall"] == 3.75
    rows = client.get(f"/api/v1/me/daily/rounds/{rd['id']}/reports", headers=me).json()
    x = rows[0]
    assert x["sessions"][0]["delta"] == 5 and x["sessions"][1]["delta"] == -30 and x["minutes_delta"] == -25
    assert x["sessions_delivered"] == 1 and x["sessions_partly"] == 1 and x["low_scores"] == 1 and x["open_escalations"] == 1
    # same device corrects; another device cannot
    assert client.post(f"/api/v1/public/daily/{token}/submit", json={**report(g_devices=4), "report_id": first["report_id"], "edit_token": first["edit_token"]}).status_code == 200
    assert client.post(f"/api/v1/public/daily/{token}/submit", json={**report(), "report_id": first["report_id"], "edit_token": "wrong"}).status_code == 403
    client.post(f"/api/v1/public/daily/{token}/submit", json=report(class_hall="Hall 3", lead_facilitator="Mohamed Sesay", sessions=[dict(s, delivered="Y", actual_start=s["planned_start"], actual_end=s["planned_end"], reason="") for s in report()["sessions"]],
                                                                   carried_over=[], quiz_administered=False, quiz_title=None, mean_score=None, pass_rate=None, practice_minutes=None, practice_comments="N/A: no tablets until day 2",
                                                                   hardest_topics=[], q_time=4, q_time_evidence=None, material_issues=[], g_power=5, g_devices=0, escalations=[]))
    client.post(f"/api/v1/public/daily/{token}/submit", json=report(training_day=2, district="Bonthe", sessions=[{"topic": "Household questionnaire: roster and demographics", "planned_start": "09:00", "planned_end": "12:00", "actual_start": "09:00", "actual_end": "12:30", "delivered": "Y", "reason": ""}],
                                                                   carried_over=[], hardest_topics=["Household questionnaire: roster and demographics"], q_content=5, q_content_evidence="Trainees quoted the rule unprompted", q_time=3, q_time_evidence=None, escalations=[{"issue": "Projector failed", "raised_to": "CCIT", "owner": "ICT", "needed_by": "today", "status": "RESOLVED"}]))

    # summary: every indicator
    s = client.get(f"/api/v1/me/daily/rounds/{rd['id']}/summary", headers=me).json()
    assert s["reports"] == 3 and s["classes"] == 2 and s["days"] == 2 and s["facilitators"] == 2 and s["districts"] == 2
    assert s["sessions"] == 5 and s["delivered"] == 4 and s["partly"] == 1 and s["delivered_pct"] == 80.0 and s["minutes_delta"] == 5 and s["carried_over"] == 1
    assert s["quizzes"] == 2 and s["mean_score"] == 72.5 and s["pass_rate"] == 81.0 and s["practice_minutes_avg"] == 60.0 and s["practice_na"] == 1
    assert s["quality"]["content"] == 4.33 and s["quality"]["time"] == 3.0 and s["quality"]["overall"] == 4.08 and s["low_scores"] == 1
    assert s["quality_distribution"]["time"][3]["count"] == 1  # one score of 2
    assert s["material_issues"] == 2 and s["issues_by_severity"][0]["count"] == 2
    assert s["logistics"]["power"] == 3.0 and s["devices_short"] == 10 and s["escalations"] == 2 and s["open_escalations"] == 1
    assert [g["label"] for g in s["by_day"]] == ["Day 1", "Day 2"] and s["by_day"][0]["reports"] == 2 and s["by_day"][0]["delivered_pct"] == 75.0
    topics = {t["topic"]: t for t in s["topics"]}
    assert topics["Household listing on CAPI"]["partly"] == 1 and topics["Household listing on CAPI"]["carried_over"] == 1 and topics["Household listing on CAPI"]["hardest"] == 1 and topics["Household listing on CAPI"]["day"] == 1
    assert s["hardest_topics"][0]["count"] == 1 and len(s["issues_log"]) == 2 and len(s["escalations_log"]) == 2 and len(s["evidence_log"]) == 5 and len(s["carried_over_log"]) == 1
    f = client.get(f"/api/v1/me/daily/rounds/{rd['id']}/summary?district=Bonthe", headers=me).json()
    assert f["reports"] == 1 and f["filters"]["district"] == "Bonthe"
    assert client.get(f"/api/v1/me/daily/rounds/{rd['id']}/summary?facilitator=mohamed%20sesay", headers=me).json()["reports"] == 1

    # escalation follow-up, manager edit, export, delete, close
    rid = first["report_id"]
    e = client.patch(f"/api/v1/me/daily/rounds/{rd['id']}/reports/{rid}/escalation", json={"index": 0, "status": "RESOLVED"}, headers=me)
    assert e.status_code == 200 and e.json()["open_escalations"] == 0 and e.json()["edited_by_name"] == "me.officer"
    assert client.get(f"/api/v1/me/daily/rounds/{rd['id']}/summary", headers=me).json()["open_escalations"] == 0
    assert client.put(f"/api/v1/me/daily/rounds/{rd['id']}/reports/{rid}", json=report(q_engagement=3, q_engagement_evidence=None), headers=me).json()["overall"] == 3.25
    assert client.get(f"/api/v1/me/daily/rounds/{rd['id']}/reports/{rid}", headers=dqm).status_code == 403
    x = client.get(f"/api/v1/me/daily/rounds/{rd['id']}/export?format=xlsx", headers=me)
    assert x.status_code == 200 and x.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert client.get(f"/api/v1/me/daily/rounds/{rd['id']}/export?format=pdf&district=Bo", headers=me).status_code == 200
    assert client.delete(f"/api/v1/me/daily/rounds/{rd['id']}/reports/{rid}", headers=me).status_code == 204
    assert client.get(f"/api/v1/me/daily/rounds/{rd['id']}/summary", headers=me).json()["reports"] == 2
    assert client.delete(f"/api/v1/me/daily/rounds/{rd['id']}", headers=me).status_code == 409
    assert client.patch(f"/api/v1/me/daily/rounds/{rd['id']}", json={"status": "CLOSED"}, headers=me).status_code == 200
    assert client.post(f"/api/v1/public/daily/{token}/submit", json=report()).status_code == 409


def test_daily_evaluation_admin_role(client, admin):
    """The Daily Evaluation Admin role sees the daily module only: no training evaluations, no field monitoring, no dashboard."""
    assert client.post("/api/v1/admin/users", json={"username": "daily.admin", "password": "Password123", "full_name": "Daily Admin", "role": "ME_DAILY"}, headers=admin).status_code == 201
    d = login(client, "daily.admin", "Password123")
    perms = set(d["user"]["permissions"])
    assert {"me_daily.view", "me_daily.manage"} <= perms and not {"me.view", "mefm.view", "dashboard.view"} & perms
    h = auth(d["access_token"])
    assert client.post("/api/v1/me/daily/rounds", json={"title": "Master training, Freetown", "phase": "MASTER"}, headers=h).status_code == 201
    assert client.get("/api/v1/me/daily/rounds", headers=h).status_code == 200
    assert client.get("/api/v1/me/evaluations", headers=h).status_code == 403
    assert client.get("/api/v1/mefm/overview", headers=h).status_code == 403
    assert client.get("/api/v1/admin/users", headers=h).status_code == 403


def test_agenda_template_and_upload(client, admin):
    """The bundled 10-day Master Training agenda loads at creation; an agenda workbook in the same layout can be uploaded."""
    import io

    from openpyxl import Workbook

    me = me_user(client, admin)
    t = client.get("/api/v1/me/daily/agenda-templates", headers=me).json()
    assert [x["key"] for x in t] == ["MASTER_10_DAYS"] and t[0]["days"] == 10 and len(t[0]["items"]) == 71 and t[0]["day_titles"]["3"].startswith("CAPI PRACTICE 1")
    r = client.post("/api/v1/me/daily/rounds", json={"title": "Master training, Freetown, cohort 1", "phase": "MASTER", "agenda_template": "MASTER_10_DAYS"}, headers=me)
    assert r.status_code == 201 and r.json()["agenda_items"] == 71 and r.json()["agenda_days"] == 10, r.text
    agenda = client.get(f"/api/v1/me/daily/rounds/{r.json()['id']}/agenda", headers=me).json()
    day2 = [a for a in agenda if a["day"] == 2]
    assert day2[0]["topic"] == "Assessment" and day2[0]["planned_start"] == "08:30" and any("8.1 Introduction" in (a["details"] or "") for a in day2)
    assert client.post("/api/v1/me/daily/rounds", json={"title": "x y z", "phase": "MASTER", "agenda_template": "NOPE"}, headers=me).status_code == 404
    # the public page carries the agenda with details
    pub = client.get(f"/api/v1/public/daily/{r.json()['token']}").json()
    assert len(pub["agenda"]) == 71 and pub["agenda"][0]["responsible"] == "Moses Johnson & Facilitators"

    # upload: a workbook in the Master Training layout
    wb = Workbook()
    ws = wb.active
    for row in [["DAY1 - OPENING"], ["TIME", "D", "DURATION", "ACTIVITY", "RESPONSIBLE PERSON(S)"], ["08:00 - 08:30", "5hrs", "30mins", "Attendance and breakfast", "All"],
                ["08:30 – 10:00", None, "1hr 30mins", "·   Chapter 1 – General Information:", "All Facilitators"], [None, None, None, "1.1 Introduction; 1.2 Objectives", None],
                ["13:00 - 14:00", "1hr", "1hr", "Lunch", "All"], ["DAY2 - CONCEPTS"], ["09:00 - 12:00", None, "3hrs", "Chapter 11 – Questionnaires", "All Facilitators"]]:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    up = client.post("/api/v1/me/daily/agenda/parse", files={"file": ("agenda.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, headers=me)
    assert up.status_code == 200, up.text
    parsed = up.json()
    assert parsed["days"] == 2 and [i["topic"] for i in parsed["items"]] == ["Chapter 1 – General Information", "Chapter 11 – Questionnaires"]
    assert parsed["items"][0]["planned_start"] == "08:30" and parsed["items"][0]["planned_end"] == "10:00" and parsed["items"][0]["details"] == "1.1 Introduction; 1.2 Objectives"
    csv_text = "day,topic,planned_start,planned_end\n1,Opening,09:00,10:00\n2,Listing practical,10:00,13:00\n"
    up = client.post("/api/v1/me/daily/agenda/parse", files={"file": ("agenda.csv", csv_text, "text/csv")}, headers=me)
    assert up.status_code == 200 and len(up.json()["items"]) == 2 and up.json()["items"][1]["planned_end"] == "13:00"
    assert client.post("/api/v1/me/daily/agenda/parse", files={"file": ("x.csv", "nothing here\n", "text/csv")}, headers=me).status_code == 400
