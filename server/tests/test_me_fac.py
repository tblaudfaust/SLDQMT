"""Facilitator assessment: a training with the chapters per day shared by link, the daily trainer rating with its
scoring (section A out of 20 with a band, section B over the sections rated, overall %), corrections from the
same device, one rating per monitor, trainer, hall and day, the summary by district, hall, day and trainer, exports,
and access by the me_fac rights (M&E and the Daily Evaluation Admin manage it)."""

from datetime import date, timedelta

from tests.conftest import auth, login


def user(client, admin, username, role):
    r = client.post("/api/v1/admin/users", json={"username": username, "password": "Password123", "full_name": username, "role": role}, headers=admin)
    assert r.status_code == 201, r.text
    return auth(login(client, username, "Password123")["access_token"])


def rating(**over):
    body = {"assessment_date": date.today().isoformat(), "training_day": 2, "district": "Bo", "hall": "Hall 1", "monitor_name": "Mariama Jalloh", "trainer_name": "Mohamed Kamara",
            "s_technical": 4, "s_clarity": 3, "s_practical": 4, "s_participation": 3, "s_time": 2,
            "sections": [{"topic": "Chapter 6 – Preliminary Work in the Enumeration Area", "rating": 4}, {"topic": "Chapter 7 – Use of Maps, GIS and Enumeration Area Boundaries", "rating": 3}, {"topic": "Chapter 9 – Achieving Complete Coverage", "rating": None}],
            "strengths": "Clear examples from the field", "improvements": "Ran 20 minutes over on chapter 7", "comments": None}
    body.update(over)
    return body


def test_rounds_agenda_ratings_summary_export_and_access(client, admin):
    me = user(client, admin, "me.officer", "ME")
    dqm = user(client, admin, "dqm.wau", "NATIONAL_DQM")
    templates = client.get("/api/v1/me/facilitators/agenda-templates", headers=me).json()
    t2026 = next(t for t in templates if t["key"] == "TRAINING_2026")
    assert t2026["days"] == 10 and all("recap" not in i["topic"].lower() and "quiz" not in i["topic"].lower() for i in t2026["items"])

    r = client.post("/api/v1/me/facilitators/rounds", json={"title": "Master Trainers session, October 2026", "phase": "MASTER", "period_start": "2026-10-19", "period_end": "2026-10-30", "agenda_template": "TRAINING_2026"}, headers=me)
    assert r.status_code == 201, r.text
    rd = r.json()
    assert rd["agenda_days"] == 10 and rd["agenda_items"] > 30 and rd["share_url"] is None
    assert client.post("/api/v1/me/facilitators/rounds", json={"title": "master trainers session, october 2026", "phase": "MASTER"}, headers=me).status_code == 409
    assert client.get("/api/v1/me/facilitators/rounds", headers=dqm).status_code == 403
    token = rd["token"]

    # the chapters per day can be replaced
    a = client.put(f"/api/v1/me/facilitators/rounds/{rd['id']}/agenda", json=[{"day": 2, "topic": "Chapter 6 – Preliminary Work in the Enumeration Area"}, {"day": 2, "topic": "Chapter 7 – Use of Maps, GIS and Enumeration Area Boundaries", "details": "7.1 to 7.5"}, {"day": 3, "topic": "Chapter 11 – Household questionnaire"}], headers=me)
    assert a.status_code == 200 and [x["position"] for x in a.json()] == [1, 2, 1]
    pub = client.get(f"/api/v1/public/assess/{token}")
    assert pub.status_code == 200 and len(pub.json()["agenda"]) == 3 and len(pub.json()["form"]["criteria"]) == 5
    assert client.get("/api/v1/public/assess/not-a-token").status_code == 404

    # scoring: A = 16 (Good), B = 7 of 8 rated, overall = 23/28 = 82.1 % (Good)
    first = client.post(f"/api/v1/public/assess/{token}/submit", json=rating())
    assert first.status_code == 200, first.text
    f = first.json()
    assert f["section_a_total"] == 16 and f["score_pct"] == 82.1 and f["band"] == "GOOD"
    assert client.post(f"/api/v1/public/assess/{token}/submit", json=rating(assessment_date=(date.today() + timedelta(days=1)).isoformat())).status_code == 400
    assert client.post(f"/api/v1/public/assess/{token}/submit", json=rating(s_time=5)).status_code == 422
    # the same monitor rating the same trainer in the same hall on the same day: refused, corrected instead
    assert client.post(f"/api/v1/public/assess/{token}/submit", json=rating(s_time=4)).status_code == 409
    corrected = client.post(f"/api/v1/public/assess/{token}/submit", json={**rating(s_time=4), "assessment_id": f["assessment_id"], "edit_token": f["edit_token"]})
    assert corrected.status_code == 200 and corrected.json()["section_a_total"] == 18 and corrected.json()["band"] == "EXCELLENT"
    assert client.post(f"/api/v1/public/assess/{token}/submit", json={**rating(), "assessment_id": f["assessment_id"], "edit_token": "wrong"}).status_code == 403

    # more ratings: another hall, another district, a weak trainer, another day
    client.post(f"/api/v1/public/assess/{token}/submit", json=rating(hall="Hall 2", trainer_name="Fatmata Koroma", s_technical=2, s_clarity=2, s_practical=1, s_participation=2, s_time=2, sections=[]))
    client.post(f"/api/v1/public/assess/{token}/submit", json=rating(district="Kenema", hall="Hall A", monitor_name="Ibrahim Conteh", trainer_name="Sahr Bockarie", s_technical=4, s_clarity=4, s_practical=4, s_participation=4, s_time=4))
    client.post(f"/api/v1/public/assess/{token}/submit", json=rating(district=None, hall="Main hall", monitor_name="Ibrahim Conteh", trainer_name="Aminata Sesay", training_day=3, sections=[{"topic": "Chapter 11 – Household questionnaire", "rating": 3}]))

    s = client.get(f"/api/v1/me/facilitators/rounds/{rd['id']}/summary", headers=me).json()
    assert s["assessments"] == 4 and s["trainers"] == 4 and s["halls"] == 4 and s["districts"] == 3 and s["days"] == 2 and s["monitors"] == 2
    assert [b["count"] for b in s["band_counts"]] == [2, 1, 1, 0]  # Excellent, Good, Fair (9 of 20), Needs improvement
    assert s["low_scores"] == 2 and len(s["needs_attention"]) == 2 and s["needs_attention"][0]["label"] == "Fatmata Koroma"  # Aminata has a 2 for time
    assert [g["label"] for g in s["by_district"]] == ["Bo", "Kenema", "National / HQ"]
    bo = next(g for g in s["by_district"] if g["label"] == "Bo")
    assert bo["assessments"] == 2 and bo["trainers"] == 2 and bo["halls"] == 2 and bo["lowest_criterion"] == "Clarity"  # clarity and practical tie at 2.5
    assert [g["label"] for g in s["by_hall"]] == ["Bo · Hall 1", "Bo · Hall 2", "Kenema · Hall A", "National / HQ · Main hall"]
    assert s["by_trainer"][0]["label"] == "Sahr Bockarie" and s["by_trainer"][0]["mean_pct"] == 96.4  # 20 + 7 of 28
    assert [t["topic"] for t in s["topics"]][0].startswith("Chapter 6") and s["topics"][0]["mean"] == 4.0
    assert s["criteria"][2]["key"] == "practical" and s["criteria"][2]["distribution"][0]["count"] == 1  # one score of 1
    # filters
    assert client.get(f"/api/v1/me/facilitators/rounds/{rd['id']}/summary?district=Kenema", headers=me).json()["assessments"] == 1
    assert client.get(f"/api/v1/me/facilitators/rounds/{rd['id']}/summary?district=HQ", headers=me).json()["assessments"] == 1
    assert client.get(f"/api/v1/me/facilitators/rounds/{rd['id']}/summary?hall=hall%202", headers=me).json()["assessments"] == 1
    assert client.get(f"/api/v1/me/facilitators/rounds/{rd['id']}/summary?training_day=3", headers=me).json()["assessments"] == 1
    assert client.get(f"/api/v1/me/facilitators/rounds/{rd['id']}/assessments?trainer=sahr%20bockarie", headers=me).json()[0]["band_label"] == "Excellent"

    # the M&E account edits and removes a rating; exports work; the viewer without rights is refused
    rows = client.get(f"/api/v1/me/facilitators/rounds/{rd['id']}/assessments", headers=me).json()
    rid = next(x["id"] for x in rows if x["trainer_name"] == "Fatmata Koroma")
    assert client.put(f"/api/v1/me/facilitators/rounds/{rd['id']}/assessments/{rid}", json=rating(hall="Hall 2", trainer_name="Fatmata Koroma", s_practical=3, sections=[]), headers=me).json()["section_a_total"] == 15
    assert client.get(f"/api/v1/me/facilitators/rounds/{rd['id']}/assessments/{rid}", headers=dqm).status_code == 403
    x = client.get(f"/api/v1/me/facilitators/rounds/{rd['id']}/export?format=xlsx", headers=me)
    assert x.status_code == 200 and x.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert client.get(f"/api/v1/me/facilitators/rounds/{rd['id']}/export?format=pdf&district=Bo", headers=me).status_code == 200
    assert client.delete(f"/api/v1/me/facilitators/rounds/{rd['id']}/assessments/{rid}", headers=me).status_code == 204
    assert client.get(f"/api/v1/me/facilitators/rounds/{rd['id']}/summary", headers=me).json()["assessments"] == 3
    # a closed assessment refuses new ratings; a round with ratings cannot be deleted
    assert client.patch(f"/api/v1/me/facilitators/rounds/{rd['id']}", json={"status": "CLOSED"}, headers=me).json()["status"] == "CLOSED"
    assert client.post(f"/api/v1/public/assess/{token}/submit", json=rating(trainer_name="New Trainer")).status_code == 409
    assert client.delete(f"/api/v1/me/facilitators/rounds/{rd['id']}", headers=me).status_code == 409


def test_daily_evaluation_admin_manages_facilitator_assessment(client, admin):
    daily = user(client, admin, "daily.admin", "ME_DAILY")
    r = client.post("/api/v1/me/facilitators/rounds", json={"title": "ToT Southern region", "phase": "TOT"}, headers=daily)
    assert r.status_code == 201, r.text
    assert client.get("/api/v1/me/facilitators/rounds", headers=daily).json()[0]["assessments"] == 0
    assert client.delete(f"/api/v1/me/facilitators/rounds/{r.json()['id']}", headers=daily).status_code == 204
