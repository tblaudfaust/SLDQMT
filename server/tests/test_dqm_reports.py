from datetime import date, timedelta

import pytest

from tests.conftest import auth, login


@pytest.fixture
def users(client, admin, geo):
    wau = geo["districts"]["WAU"]["id"]
    war = geo["districts"]["WAR"]["id"]
    regions = client.get("/api/v1/admin/reference/regions", headers=admin).json()
    western = regions[0]["id"]
    for body in [
        {"username": "dqm.wau", "password": "Password123", "full_name": "District DQM WAU", "role": "DISTRICT_DQM", "district_ids": [wau]},
        {"username": "dqm.war", "password": "Password123", "full_name": "District DQM WAR", "role": "DISTRICT_DQM", "district_ids": [war]},
        {"username": "regional", "password": "Password123", "full_name": "Regional Western", "role": "REGIONAL", "region_ids": [western]},
        {"username": "national", "password": "Password123", "full_name": "National DQM", "role": "NATIONAL_DQM"},
    ]:
        assert client.post("/api/v1/admin/users", json=body, headers=admin).status_code == 201
    return {
        "wau": auth(login(client, "dqm.wau", "Password123")["access_token"]),
        "war": auth(login(client, "dqm.war", "Password123")["access_token"]),
        "regional": auth(login(client, "regional", "Password123")["access_token"]),
        "national": auth(login(client, "national", "Password123")["access_token"]),
        "wau_id": wau, "war_id": war, "western": western,
    }


def report_body(day=None, **over):
    body = {
        "report_date": (day or date.today()).isoformat(),
        "period": "ENUMERATION",
        "day_number": 1,
        "teams_reviewed": 12,
        "teams_certified": 9,
        "teams_pending": 3,
        "executive_summary": "Good progress",
        "reinterviews_received": 30,
        "reinterviews_received_pending": 4,
        "reinterviews_certified": 22,
        "reinterviews_certified_pending": 2,
        "error_profile": [
            {"band": "LOW", "ea_code": "WAU-SA01-EA01", "team": "SA01", "likely_cause": "", "correction": "", "remarks": ""},
            {"band": "HIGH", "ea_code": "WAU-SA01-EA02", "team": "SA01", "likely_cause": "Enumerator skipping questions", "correction": "Coaching", "remarks": ""},
        ],
        "system_issues": [
            {"issue_type": "GPS", "ea_code": "WAU-SA01-EA02", "finding": "No fix under canopy", "referred_to": "GIS", "action_taken": "Retake at clearing", "resolution_status": "OPEN"},
            {"issue_type": "SYNC", "ea_code": "", "finding": "Bluetooth pairing", "referred_to": "IT", "action_taken": "Re-paired", "resolution_status": "RESOLVED"},
        ],
        "lessons": [{"quality_area": "GPS", "lesson": "Take GPS in the open", "risk": "Wrong EA", "control": "Retrain"}],
        "sa_performance": [{"sa": "SA01", "assessment": "On track"}],
    }
    body.update(over)
    return body


def test_district_creates_submits_and_national_receives(client, users):
    r = client.post("/api/v1/dqm-reports", json=report_body(), headers=users["wau"])
    assert r.status_code == 201, r.text
    rep = r.json()
    assert rep["district_id"] == users["wau_id"] and rep["status"] == "DRAFT"
    assert rep["prepared_name"] == "District DQM WAU"
    assert rep["teams_pending"] == 3
    assert len(rep["error_profile"]) == 2 and rep["system_issues"][0]["issue_type"] == "GPS"

    # Same day again is rejected
    assert client.post("/api/v1/dqm-reports", json=report_body(), headers=users["wau"]).status_code == 409
    # Another district cannot be targeted
    assert client.post("/api/v1/dqm-reports", json=report_body(day=date.today() - timedelta(days=1), district_id=users["war_id"]), headers=users["wau"]).status_code == 403

    # Edit while draft
    r = client.put(f"/api/v1/dqm-reports/{rep['id']}", json=report_body(teams_certified=10), headers=users["wau"])
    assert r.status_code == 200 and r.json()["teams_certified"] == 10

    # Regional cannot submit or edit, but can read
    assert client.post(f"/api/v1/dqm-reports/{rep['id']}/submit", headers=users["regional"]).status_code == 403
    assert client.get(f"/api/v1/dqm-reports/{rep['id']}", headers=users["regional"]).status_code == 200

    # National cannot receive before submission
    assert client.post(f"/api/v1/dqm-reports/{rep['id']}/receive", json={}, headers=users["national"]).status_code == 409

    r = client.post(f"/api/v1/dqm-reports/{rep['id']}/submit", headers=users["wau"])
    assert r.status_code == 200 and r.json()["status"] == "SUBMITTED" and r.json()["submitted_at"]

    assert client.post(f"/api/v1/dqm-reports/{rep['id']}/receive", json={"comment": "Noted"}, headers=users["regional"]).status_code == 403
    r = client.post(f"/api/v1/dqm-reports/{rep['id']}/receive", json={"comment": "Noted"}, headers=users["national"])
    assert r.status_code == 200 and r.json()["status"] == "RECEIVED" and r.json()["received_name"] == "National DQM"

    # Locked after receipt
    assert client.put(f"/api/v1/dqm-reports/{rep['id']}", json=report_body(), headers=users["wau"]).status_code == 409


def test_scope_on_listing(client, users):
    client.post("/api/v1/dqm-reports", json=report_body(), headers=users["wau"])
    client.post("/api/v1/dqm-reports", json=report_body(), headers=users["war"])
    assert len(client.get("/api/v1/dqm-reports", headers=users["wau"]).json()) == 1
    assert len(client.get("/api/v1/dqm-reports", headers=users["war"]).json()) == 1
    assert len(client.get("/api/v1/dqm-reports", headers=users["regional"]).json()) == 2
    rows = client.get("/api/v1/dqm-reports", headers=users["national"]).json()
    assert len(rows) == 2 and rows[0]["high_errors"] == 1 and rows[0]["open_issues"] == 1
    # A WAR report is not visible to the WAU officer by id
    war_id = [r for r in rows if r["district_id"] == users["war_id"]][0]["id"]
    assert client.get(f"/api/v1/dqm-reports/{war_id}", headers=users["wau"]).status_code == 404


def test_regional_and_national_summaries(client, users):
    yesterday = date.today() - timedelta(days=1)
    r1 = client.post("/api/v1/dqm-reports", json=report_body(day=yesterday, teams_reviewed=8, teams_certified=5), headers=users["wau"]).json()
    r2 = client.post("/api/v1/dqm-reports", json=report_body(), headers=users["wau"]).json()  # today, cumulative 12/9
    client.post(f"/api/v1/dqm-reports/{r2['id']}/submit", headers=users["wau"])

    s = client.get("/api/v1/dqm-reports/summary", params={"level": "region"}, headers=users["regional"]).json()
    assert s["level"] == "region" and s["region"] == "Western"
    labels = {row["label"]: row for row in s["rows"]}
    assert set(labels) == {"Western Area Urban", "Western Area Rural"}
    wau = labels["Western Area Urban"]
    assert wau["reports"] == 2 and wau["submitted"] == 1 and wau["days_covered"] == 2
    assert wau["teams_reviewed"] == 12 and wau["teams_certified"] == 9  # latest cumulative, not summed
    assert wau["reinterviews_received"] == 60 and wau["errors_high"] == 2 and wau["issues_open"] == 2
    assert labels["Western Area Rural"]["reports"] == 0
    assert s["totals"]["reports"] == 2 and s["totals"]["teams_reviewed"] == 12
    assert s["expected_units"] == 2 and s["reported_today"] == 1 and s["missing_today"] == ["Western Area Rural"]

    # Regional staff cannot see the national summary; National can
    assert client.get("/api/v1/dqm-reports/summary", params={"level": "national"}, headers=users["regional"]).status_code == 403
    n = client.get("/api/v1/dqm-reports/summary", params={"level": "national"}, headers=users["national"]).json()
    assert n["level"] == "national" and [row["label"] for row in n["rows"]] == ["Western"]
    assert n["rows"][0]["reports"] == 2 and n["missing_today"] == ["Western Area Rural"]

    # Date filter
    d = client.get("/api/v1/dqm-reports/summary", params={"level": "region", "date_from": date.today().isoformat()}, headers=users["national"], ).status_code
    assert d == 400  # region_id required for national user asking a regional summary
    d = client.get("/api/v1/dqm-reports/summary", params={"level": "region", "region_id": users["western"], "date_from": date.today().isoformat()}, headers=users["national"]).json()
    assert d["totals"]["reports"] == 1

    # Exports
    for fmt in ("pdf", "xlsx"):
        assert client.get(f"/api/v1/dqm-reports/{r1['id']}/export", params={"format": fmt}, headers=users["regional"]).status_code == 200
        assert client.get("/api/v1/dqm-reports/summary/export", params={"level": "national", "format": fmt}, headers=users["national"]).status_code == 200


def test_options_reflect_role(client, users):
    assert client.get("/api/v1/dqm-reports/options", headers=users["wau"]).json()["can_edit"] is True
    o = client.get("/api/v1/dqm-reports/options", headers=users["regional"]).json()
    assert o["can_edit"] is True and o["can_create"] is False and o["can_receive"] is False
    assert client.get("/api/v1/dqm-reports/options", headers=users["national"]).json()["can_receive"] is True


def test_one_report_per_officer_per_district_per_day(client, admin, users):
    """Several DQM officers work in one district: each sends their own daily report, but not two for the same day."""
    body = {"district_id": users["wau_id"], "report_date": date.today().isoformat(), "period": "ENUMERATION", "day_number": 1, "prepared_name": "DQM WAU"}
    first = client.post("/api/v1/dqm-reports", json=body, headers=users["wau"])
    assert first.status_code == 201, first.text
    dup = client.post("/api/v1/dqm-reports", json=body, headers=users["wau"])
    assert dup.status_code == 409 and f"(id {first.json()['id']})" in dup.json()["detail"]

    # a second officer in the same district can still send theirs
    assert client.post("/api/v1/admin/users", json={"username": "dqm.wau2", "password": "Password123", "full_name": "Second DQM WAU", "role": "DISTRICT_DQM", "district_ids": [users["wau_id"]]}, headers=admin).status_code == 201
    second = auth(login(client, "dqm.wau2", "Password123")["access_token"])
    other = client.post("/api/v1/dqm-reports", json={**body, "prepared_name": "Second DQM WAU"}, headers=second)
    assert other.status_code == 201, other.text
    assert client.post("/api/v1/dqm-reports", json=body, headers=second).status_code == 409
    rows = client.get("/api/v1/dqm-reports", headers=users["national"]).json()
    assert len([r for r in rows if r["district_id"] == users["wau_id"]]) == 2
    assert len({r["created_by"] for r in rows if r["district_id"] == users["wau_id"]}) == 2

    # a report cannot be dated in the future
    future = client.post("/api/v1/dqm-reports", json={**body, "report_date": (date.today() + timedelta(days=1)).isoformat()}, headers=users["wau"])
    assert future.status_code == 400 and "future" in future.json()["detail"]
