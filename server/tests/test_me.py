"""Monitoring & Evaluation: evaluations, the public evaluation page (register + submit with routing), results, access."""

from tests.conftest import auth, login


def me_user(client, admin):
    r = client.post("/api/v1/admin/users", json={"username": "me.officer", "password": "Password123", "full_name": "M&E Officer", "role": "ME"}, headers=admin)
    assert r.status_code == 201, r.text
    data = login(client, "me.officer", "Password123")
    return auth(data["access_token"]), data["user"]


def trainee_answers(**over):
    a = {
        "A00": "2", "A01": "2", "A02": "2", "A03": "2", "A04": "Bo", "A05": "Stats SL", "A06": "0", "A07": "3", "A08": "1", "A09": "4",
        "B07": "1", "H01": "2", "H02": "4", "H03": "4", "H04": "2", "H05": "2", "H06": "1", "H07": "2", "H08": ["CAPI/tablet", "Synchronisation"],
        "I01": "The practical CAPI exercises", "I03": "More time on synchronisation",
    }
    for sec, n in (("B", 6), ("C", 7), ("D", 12), ("E", 9), ("F", 4), ("G", 6)):
        for i in range(1, n + 1):
            a[f"{sec}{i:02d}"] = "4"
    a["G08"] = "5"  # DQM only
    a["E04"] = "2"
    a.update(over)
    return a


def trainer_answers(**over):
    a = {"A00": "1", "A02": "1", "A03": "3", "A04": "Bo", "A05": "Stats SL", "J01": "Cohort Bo-2", "J02": 25, "J10": "3", "J11": "1", "J12_n": 3, "J12_names": "FM-Bo-004, FM-Bo-009", "J13": ["CAPI/tablet"], "J14": "Extra tablet practice"}
    for i in range(3, 10):
        a[f"J{i:02d}"] = "4"
    a.update(over)
    return a


def test_me_user_sees_only_me_and_runs_an_evaluation(client, admin):
    me, profile = me_user(client, admin)
    assert set(profile["permissions"]) == {"me.view", "me.manage"}
    assert client.get("/api/v1/dashboard/summary", headers=me).status_code == 403
    assert client.get("/api/v1/admin/users", headers=me).status_code == 403

    r = client.post("/api/v1/me/evaluations", json={"title": "Online training, cohort 1", "training_mode": "ONLINE", "period_start": "2026-09-29", "period_end": "2026-10-09"}, headers=me)
    assert r.status_code == 201, r.text
    ev = r.json()
    token = ev["token"]
    assert ev["status"] == "OPEN" and ev["registered"] == 0

    # the public page needs no sign-in and carries the questionnaire
    pub = client.get(f"/api/v1/public/evaluations/{token}")
    assert pub.status_code == 200 and pub.json()["title"] == ev["title"]
    assert [s["code"] for s in pub.json()["form"]["sections"]] == list("ABCDEFGHIJ")
    assert client.get("/api/v1/public/evaluations/not-a-token").status_code == 404

    # register: phone is mandatory and validated, email too
    r = client.post(f"/api/v1/public/evaluations/{token}/register", json={"full_name": "Aminata Sesay", "email": "aminata@example.com", "phone": "not-a-phone"})
    assert r.status_code == 400
    r = client.post(f"/api/v1/public/evaluations/{token}/register", json={"full_name": "Aminata Sesay", "email": "aminata@example.com", "phone": "+232 77 000 001"})
    assert r.status_code == 200, r.text
    reg = r.json()
    assert reg["already_submitted"] is False

    # a wrong resume token cannot submit for someone else
    r = client.post(f"/api/v1/public/evaluations/{token}/submit", json={"respondent_id": reg["respondent_id"], "resume_token": "x", "answers": trainee_answers()})
    assert r.status_code == 403

    # validation: missing required rating, 'None' combined with a topic
    bad = trainee_answers(D05=None, H08=["0", "CAPI/tablet"])
    r = client.post(f"/api/v1/public/evaluations/{token}/submit", json={"respondent_id": reg["respondent_id"], "resume_token": reg["resume_token"], "answers": bad})
    assert r.status_code == 422
    errs = r.json()["detail"]["errors"]
    assert any(e.startswith("D05") for e in errs) and any(e.startswith("H08") for e in errs)

    r = client.post(f"/api/v1/public/evaluations/{token}/submit", json={"respondent_id": reg["respondent_id"], "resume_token": reg["resume_token"], "answers": trainee_answers()})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "TRAINEE"
    # twice is refused; registering again with the same email says so
    r = client.post(f"/api/v1/public/evaluations/{token}/submit", json={"respondent_id": reg["respondent_id"], "resume_token": reg["resume_token"], "answers": trainee_answers()})
    assert r.status_code == 409
    again = client.post(f"/api/v1/public/evaluations/{token}/register", json={"full_name": "Aminata Sesay", "email": "AMINATA@example.com", "phone": "+23277000001"}).json()
    assert again["already_submitted"] is True and again["respondent_id"] == reg["respondent_id"]

    # a trainer and an observer
    t = client.post(f"/api/v1/public/evaluations/{token}/register", json={"full_name": "Trainer One", "email": "trainer@example.com", "phone": "076123456"}).json()
    r = client.post(f"/api/v1/public/evaluations/{token}/submit", json={"respondent_id": t["respondent_id"], "resume_token": t["resume_token"], "answers": trainer_answers()})
    assert r.status_code == 200 and r.json()["role"] == "TRAINER", r.text
    o = client.post(f"/api/v1/public/evaluations/{token}/register", json={"full_name": "Observer", "email": "obs@example.com", "phone": "076999999"}).json()
    r = client.post(f"/api/v1/public/evaluations/{token}/submit", json={"respondent_id": o["respondent_id"], "resume_token": o["resume_token"], "answers": {"A00": "3"}})
    assert r.status_code == 200 and r.json()["role"] == "NEITHER"

    # results
    res = client.get(f"/api/v1/me/evaluations/{ev['id']}/results", headers=me).json()
    assert res["registered"] == 3 and res["submitted"] == 3 and res["trainees"] == 1 and res["trainers"] == 1 and res["neither"] == 1
    assert res["knowledge"]["gain"] == 2.0 and res["knowledge"]["pct_positive"] == 100.0
    domains = {d["code"]: d for d in res["domains"]}
    assert domains["E"]["items"][3]["code"] == "E04" and domains["E"]["items"][3]["mean"] == 2.0 and domains["E"]["items"][3]["flag"] is True
    assert domains["G"]["n_respondents"] == 1  # G07 skipped (DQM), G08 asked
    assert domains["J"]["n_respondents"] == 1 and domains["J"]["mean"] == 4.0
    assert res["completion"]["B07"][0]["label"] == "Connectivity"
    assert res["reinforcement"]["trainees"][0]["count"] == 1 and res["reinforcement"]["trainers"][0]["label"] == "CAPI/tablet"
    assert any(f["code"] == "J14" for f in res["open_feedback"])
    assert res["weaknesses"][0]["code"] == "E04"

    # respondents list, export, close, delete a response
    people = client.get(f"/api/v1/me/evaluations/{ev['id']}/respondents", headers=me).json()
    assert len(people) == 3 and all(p["submitted_at"] for p in people)
    x = client.get(f"/api/v1/me/evaluations/{ev['id']}/export?format=xlsx", headers=me)
    assert x.status_code == 200 and x.headers["content-type"].startswith("application/vnd.openxmlformats")
    resp_id = next(p["response_id"] for p in people if p["email"] == "obs@example.com")
    assert client.delete(f"/api/v1/me/evaluations/{ev['id']}/responses/{resp_id}", headers=me).status_code == 204
    assert client.get(f"/api/v1/me/evaluations/{ev['id']}/results", headers=me).json()["submitted"] == 2
    assert client.patch(f"/api/v1/me/evaluations/{ev['id']}", json={"status": "CLOSED"}, headers=me).status_code == 200
    assert client.post(f"/api/v1/public/evaluations/{token}/register", json={"full_name": "Late", "email": "late@example.com", "phone": "076000000"}).status_code == 409


def test_in_person_mode_skips_digital_access_and_routing_rules(client, admin):
    me, _ = me_user(client, admin)
    ev = client.post("/api/v1/me/evaluations", json={"title": "In-person training", "training_mode": "IN_PERSON"}, headers=me).json()
    token = ev["token"]
    reg = client.post(f"/api/v1/public/evaluations/{token}/register", json={"full_name": "Mohamed", "email": "m@example.com", "phone": "076111111"}).json()
    # B01-B07 and A09 are not asked in person; Master Trainer answers G07 not G08; F skipped when no sessions attended
    answers = trainee_answers(A01="1", A07="1")
    for code in [f"B0{i}" for i in range(1, 8)] + ["A09", "G08"] + [f"F0{i}" for i in range(1, 5)]:
        answers.pop(code, None)
    answers["G07"] = "3"
    r = client.post(f"/api/v1/public/evaluations/{token}/submit", json={"respondent_id": reg["respondent_id"], "resume_token": reg["resume_token"], "answers": answers})
    assert r.status_code == 200, r.text
    res = client.get(f"/api/v1/me/evaluations/{ev['id']}/results", headers=me).json()
    domains = {d["code"]: d for d in res["domains"]}
    assert domains["B"]["n_respondents"] == 0 and domains["F"]["n_respondents"] == 0
    g = {i["code"]: i for i in domains["G"]["items"]}
    assert g["G07"]["n"] == 1 and g["G08"]["n"] == 0

    # a district DQM has no M&E access; an administrator has
    dqm_hdr = auth(login(client, "admin", "adminpass123")["access_token"])
    assert client.get("/api/v1/me/evaluations", headers=dqm_hdr).status_code == 200


def test_duplicate_titles_refused_and_empty_evaluations_deletable(client, admin):
    me, _ = me_user(client, admin)
    first = client.post("/api/v1/me/evaluations", json={"title": "Testing", "training_mode": "ONLINE"}, headers=me)
    assert first.status_code == 201
    dup = client.post("/api/v1/me/evaluations", json={"title": "testing", "training_mode": "ONLINE"}, headers=me)
    assert dup.status_code == 409 and "already exists" in dup.json()["detail"]
    # an evaluation without responses can be deleted; one with a response cannot
    assert client.delete(f"/api/v1/me/evaluations/{first.json()['id']}", headers=me).status_code == 204
    assert client.get("/api/v1/me/evaluations", headers=me).json() == []
    ev = client.post("/api/v1/me/evaluations", json={"title": "Testing", "training_mode": "ONLINE"}, headers=me).json()
    reg = client.post(f"/api/v1/public/evaluations/{ev['token']}/register", json={"full_name": "Observer", "email": "o@example.com", "phone": "076000001"}).json()
    assert client.post(f"/api/v1/public/evaluations/{ev['token']}/submit", json={"respondent_id": reg["respondent_id"], "resume_token": reg["resume_token"], "answers": {"A00": "3"}}).status_code == 200
    assert client.delete(f"/api/v1/me/evaluations/{ev['id']}", headers=me).status_code == 409
