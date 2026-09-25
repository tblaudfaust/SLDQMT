from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import auth, login, make_error


@pytest.fixture
def seeded(client, geo, monitor):
    now = datetime.now(timezone.utc)
    errors = [
        make_error(geo, status="RESOLVED", hours_ago=30),
        make_error(geo, hours_ago=1),  # due in ~3 h, not overdue
        make_error(geo, hours_ago=12, last_action_at=(now - timedelta(hours=12)).isoformat()),  # overdue
    ]
    r = client.post("/api/v1/sync/push", json={"device_id": monitor["device_id"], "errors": errors}, headers=monitor["headers"])
    assert r.json()["applied"] == 3
    return errors


@pytest.fixture
def district_user(client, admin, geo):
    client.post("/api/v1/admin/users", json={"username": "dqm.wau", "password": "Password123", "full_name": "District DQM", "role": "DISTRICT_DQM", "district_ids": [geo["districts"]["WAU"]["id"]]}, headers=admin)
    return auth(login(client, "dqm.wau", "Password123")["access_token"])


@pytest.fixture
def other_district_user(client, admin, geo):
    client.post("/api/v1/admin/users", json={"username": "dqm.war", "password": "Password123", "full_name": "District DQM WAR", "role": "DISTRICT_DQM", "district_ids": [geo["districts"]["WAR"]["id"]]}, headers=admin)
    return auth(login(client, "dqm.war", "Password123")["access_token"])


def test_summary_counts(client, admin, seeded):
    s = client.get("/api/v1/dashboard/summary", headers=admin).json()
    assert s["total"] == 3 and s["resolved"] == 1 and s["unresolved"] == 2
    assert s["overdue"] == 1
    assert s["resolution_rate"] == 33.3


def test_overdue_matches_summary(client, admin, seeded):
    s = client.get("/api/v1/dashboard/summary", headers=admin).json()
    rows = client.get("/api/v1/dashboard/overdue", headers=admin).json()
    assert len(rows) == s["overdue"]
    assert rows[0]["hours_overdue"] > 0


def test_scope_limits_district_user(client, district_user, other_district_user, seeded):
    mine = client.get("/api/v1/dashboard/summary", headers=district_user).json()
    theirs = client.get("/api/v1/dashboard/summary", headers=other_district_user).json()
    assert mine["total"] == 3
    assert theirs["total"] == 0
    # Asking for another district explicitly does not widen the scope.
    r = client.get("/api/v1/errors", params={"district_id": [1, 2]}, headers=other_district_user).json()
    assert r["total"] == 0


def test_field_monitor_cannot_open_dashboard(client, monitor, seeded):
    assert client.get("/api/v1/dashboard/summary", headers=monitor["headers"]).status_code == 403


def test_breakdowns_and_list(client, admin, seeded):
    assert client.get("/api/v1/dashboard/by-district", headers=admin).json()[0]["total"] == 3
    assert client.get("/api/v1/dashboard/by-category", headers=admin).json()[0]["total"] == 3
    monitors = client.get("/api/v1/dashboard/by-monitor", headers=admin).json()
    assert monitors[0]["total"] == 3 and monitors[0]["last_sync_at"] is not None
    teams = client.get("/api/v1/dashboard/by-team", headers=admin).json()
    assert teams[0]["supervisor"] == "Mohamed Kamara"
    assert sum(p["received"] for p in client.get("/api/v1/dashboard/trend", headers=admin).json()) == 3
    bands = client.get("/api/v1/dashboard/ageing", headers=admin).json()
    assert sum(b["count"] for b in bands) == 2
    page = client.get("/api/v1/errors", params={"status": "UNRESOLVED", "overdue_only": True}, headers=admin).json()
    assert page["total"] == 1 and page["items"][0]["overdue"] is True
    detail = client.get(f"/api/v1/errors/{page['items'][0]['id']}", headers=admin).json()
    assert detail["status"] == "UNRESOLVED"
    search = client.get("/api/v1/errors", params={"search": "household 12"}, headers=admin).json()
    assert search["total"] == 3


@pytest.mark.parametrize("kind", ["daily_summary", "district_register", "overdue", "category_analysis", "team_performance", "monitor_activity", "full_export"])
@pytest.mark.parametrize("fmt", ["xlsx", "pdf"])
def test_reports_generate(client, admin, seeded, kind, fmt):
    r = client.get(f"/api/v1/reports/{kind}", params={"format": fmt}, headers=admin)
    assert r.status_code == 200, r.text
    assert len(r.content) > 500
    assert kind in r.headers["content-disposition"]


def test_error_detail_report(client, admin, seeded):
    page = client.get("/api/v1/errors", headers=admin).json()
    r = client.get("/api/v1/reports/error_detail", params={"format": "pdf", "error_id": page["items"][0]["id"]}, headers=admin)
    assert r.status_code == 200
    assert client.get("/api/v1/reports/error_detail", headers=admin).status_code == 400
