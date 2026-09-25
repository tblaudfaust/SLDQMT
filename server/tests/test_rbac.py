"""Role-based access rights, per-user overrides, soft delete and the audit trail."""

from datetime import date

from tests.conftest import auth, login, make_error
from tests.test_dqm_reports import report_body, users  # noqa: F401
from tests.test_exit_checkouts import checkout_body


def test_login_returns_effective_permissions(client, users):  # noqa: F811
    me = client.get("/api/v1/auth/me", headers=users["wau"]).json()
    assert "daily_reports.create" in me["permissions"] and "daily_reports.receive" not in me["permissions"]
    nat = client.get("/api/v1/auth/me", headers=users["national"]).json()
    assert "daily_reports.receive" in nat["permissions"] and "users.manage" not in nat["permissions"]
    adm = client.get("/api/v1/auth/me", headers=auth(login(client, "admin", "adminpass123")["access_token"])).json()
    assert "roles.manage" in adm["permissions"]


def test_role_matrix_can_be_changed_and_is_audited(client, admin, users):  # noqa: F811
    m = client.get("/api/v1/admin/roles", headers=admin).json()
    assert "daily_reports.receive" not in m["roles"]["REGIONAL"]
    assert client.get("/api/v1/admin/roles", headers=users["national"]).status_code == 403

    codes = m["roles"]["REGIONAL"] + ["daily_reports.receive"]
    r = client.put("/api/v1/admin/roles/REGIONAL", json={"codes": codes}, headers=admin)
    assert r.status_code == 200 and "daily_reports.receive" in r.json()["roles"]["REGIONAL"]
    # The regional user can now receive a submitted report
    rep = client.post("/api/v1/dqm-reports", json=report_body(), headers=users["wau"]).json()
    client.post(f"/api/v1/dqm-reports/{rep['id']}/submit", headers=users["wau"])
    assert client.post(f"/api/v1/dqm-reports/{rep['id']}/receive", json={}, headers=users["regional"]).status_code == 200
    # Unknown code refused; admin cannot drop its own management rights
    assert client.put("/api/v1/admin/roles/REGIONAL", json={"codes": ["nope.x"]}, headers=admin).status_code == 400
    assert client.put("/api/v1/admin/roles/ADMIN", json={"codes": ["dashboard.view"]}, headers=admin).status_code == 400
    log = client.get("/api/v1/admin/audit", params={"action": "role.permissions"}, headers=admin).json()
    assert log and "daily_reports.receive" in log[0]["detail"] and log[0]["username"] == "admin"


def test_user_override_grant_and_revoke(client, admin, users):  # noqa: F811
    uid = client.get("/api/v1/auth/me", headers=users["wau"]).json()["id"]
    # Revoke delete from this one district officer, grant receive
    r = client.put(f"/api/v1/admin/users/{uid}/permissions", json={"grant": ["daily_reports.receive"], "revoke": ["daily_reports.delete"]}, headers=admin)
    assert r.status_code == 200
    eff = r.json()["effective"]
    assert "daily_reports.receive" in eff and "daily_reports.delete" not in eff
    rep = client.post("/api/v1/dqm-reports", json=report_body(), headers=users["wau"]).json()
    assert client.request("DELETE", f"/api/v1/dqm-reports/{rep['id']}", json={"reason": "test"}, headers=users["wau"]).status_code == 403
    client.post(f"/api/v1/dqm-reports/{rep['id']}/submit", headers=users["wau"])
    assert client.post(f"/api/v1/dqm-reports/{rep['id']}/receive", json={}, headers=users["wau"]).status_code == 200
    # Another district officer is unaffected
    rep2 = client.post("/api/v1/dqm-reports", json=report_body(), headers=users["war"]).json()
    assert client.request("DELETE", f"/api/v1/dqm-reports/{rep2['id']}", json={"reason": "wrong day"}, headers=users["war"]).status_code == 200


def test_daily_report_delete_restore_and_audit(client, admin, users):  # noqa: F811
    rep = client.post("/api/v1/dqm-reports", json=report_body(), headers=users["wau"]).json()
    assert client.request("DELETE", f"/api/v1/dqm-reports/{rep['id']}", json={"reason": ""}, headers=users["wau"]).status_code == 400
    r = client.request("DELETE", f"/api/v1/dqm-reports/{rep['id']}", json={"reason": "Entered twice"}, headers=users["wau"])
    assert r.status_code == 200 and r.json()["deleted_at"] and r.json()["delete_reason"] == "Entered twice"
    assert client.get("/api/v1/dqm-reports", headers=users["wau"]).json() == []
    assert len(client.get("/api/v1/dqm-reports", params={"deleted": True}, headers=users["wau"]).json()) == 1
    assert client.get("/api/v1/dqm-reports/summary", params={"level": "region"}, headers=users["regional"]).json()["totals"]["reports"] == 0
    # A new report for the same day is allowed while the old one is deleted; restore then clashes
    rep2 = client.post("/api/v1/dqm-reports", json=report_body(), headers=users["wau"]).json()
    assert client.post(f"/api/v1/dqm-reports/{rep['id']}/restore", headers=users["wau"]).status_code == 409
    client.request("DELETE", f"/api/v1/dqm-reports/{rep2['id']}", json={"reason": "undo"}, headers=users["wau"])
    assert client.post(f"/api/v1/dqm-reports/{rep['id']}/restore", headers=users["wau"]).status_code == 200
    log = client.get("/api/v1/admin/audit", params={"entity": "dqm_report", "entity_id": rep["id"]}, headers=admin).json()
    actions = [x["action"] for x in log]
    assert actions[:3] == ["dqm_report.restore", "dqm_report.delete", "dqm_report.create"]
    assert "Entered twice" in log[1]["detail"] and log[1]["user_name"] == "District DQM WAU"


def test_update_is_audited_with_field_diff(client, admin, users):  # noqa: F811
    rep = client.post("/api/v1/dqm-reports", json=report_body(teams_certified=9), headers=users["wau"]).json()
    client.put(f"/api/v1/dqm-reports/{rep['id']}", json=report_body(teams_certified=11), headers=users["wau"])
    log = client.get("/api/v1/admin/audit", params={"action": "dqm_report.update"}, headers=admin).json()
    assert '"teams_certified": [9, 11]' in log[0]["detail"]


def test_error_edit_delete_restore_from_dashboard(client, admin, geo, monitor, users):  # noqa: F811
    e = make_error(geo)
    client.post("/api/v1/sync/push", json={"device_id": monitor["device_id"], "errors": [e]}, headers=monitor["headers"])
    r = client.patch(f"/api/v1/errors/{e['id']}", json={"status": "RESOLVED", "action_taken": "Confirmed fixed in CSPro", "note": "Checked with supervisor"}, headers=users["wau"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "RESOLVED" and body["version"] == 2 and body["next_follow_up_at"] is None
    assert body["activity"][-1]["comments"] == "Checked with supervisor"
    # Regional user in scope can edit too; a field monitor cannot use the dashboard
    assert client.patch(f"/api/v1/errors/{e['id']}", json={"comments": "seen"}, headers=users["regional"]).status_code == 200
    assert client.patch(f"/api/v1/errors/{e['id']}", json={"comments": "x"}, headers=monitor["headers"]).status_code == 403
    # The tablet receives the dashboard edit at its next pull (client_updated_at moved forward)
    pulled = client.get("/api/v1/sync/pull", params={"device_id": monitor["device_id"]}, headers=monitor["headers"]).json()
    assert pulled["errors"][0]["status"] == "RESOLVED" and pulled["errors"][0]["client_updated_at"] > e["client_updated_at"]

    d = client.request("DELETE", f"/api/v1/errors/{e['id']}", json={"reason": "Duplicate of another error"}, headers=users["wau"])
    assert d.status_code == 200 and d.json()["deleted_at"]
    assert client.get("/api/v1/dashboard/summary", headers=admin).json()["total"] == 0
    assert client.get("/api/v1/errors", params={"deleted": True}, headers=admin).json()["total"] == 1
    # The tablet learns about the deletion and cannot push it back
    pulled = client.get("/api/v1/sync/pull", params={"device_id": monitor["device_id"]}, headers=monitor["headers"]).json()
    assert pulled["errors"][0]["deleted_at"]
    pushed = client.post("/api/v1/sync/push", json={"device_id": monitor["device_id"], "errors": [dict(e, client_updated_at="2030-01-01T00:00:00Z")]}, headers=monitor["headers"]).json()
    assert pushed["receipts"][0]["reason"] == "DELETED"
    assert client.post(f"/api/v1/errors/{e['id']}/restore", headers=users["wau"]).status_code == 200
    assert client.get("/api/v1/dashboard/summary", headers=admin).json()["total"] == 1
    log = client.get("/api/v1/admin/audit", params={"entity": "error"}, headers=admin).json()
    assert [x["action"] for x in log[:4]] == ["error.restore", "error.delete", "error.update", "error.update"]
    assert '"status": ["UNRESOLVED", "RESOLVED"]' in log[3]["detail"]


def test_checkout_delete_and_audit(client, admin, users):  # noqa: F811
    c = client.post("/api/v1/exit-checkouts", json=checkout_body(), headers=users["wau"]).json()
    assert client.request("DELETE", f"/api/v1/exit-checkouts/{c['id']}", json={"reason": "Wrong person"}, headers=users["regional"]).status_code == 200
    assert client.get("/api/v1/exit-checkouts", headers=users["wau"]).json() == []
    assert client.get("/api/v1/exit-checkouts/summary", params={"level": "district"}, headers=users["wau"]).json()["totals"]["total"] == 0
    assert client.post(f"/api/v1/exit-checkouts/{c['id']}/restore", headers=users["wau"]).status_code == 200
    log = client.get("/api/v1/admin/audit", params={"entity": "exit_checkout", "entity_id": c["id"]}, headers=admin).json()
    assert [x["action"] for x in log[:2]] == ["exit_checkout.restore", "exit_checkout.delete"]
    assert log[1]["user_name"] == "Regional Western"


def test_audit_filters_and_access(client, admin, users):  # noqa: F811
    assert client.get("/api/v1/admin/audit", headers=users["regional"]).status_code == 403
    assert client.get("/api/v1/admin/audit", headers=users["national"]).status_code == 200
    today = date.today().isoformat()
    rows = client.get("/api/v1/admin/audit", params={"action": "auth.login", "date_from": today, "date_to": today}, headers=admin).json()
    assert rows and all(r["action"] == "auth.login" for r in rows)
    actions = client.get("/api/v1/admin/audit/actions", headers=admin).json()
    assert "auth.login" in actions and "user.create" in actions
