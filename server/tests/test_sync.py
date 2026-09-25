import uuid
from datetime import datetime, timedelta, timezone

from tests.conftest import auth, login, make_error


def push(client, monitor, **payload):
    body = {"device_id": monitor["device_id"], "app_version": "0.1.0", "errors": [], "follow_ups": [], "activity": []}
    body.update(payload)
    r = client.post("/api/v1/sync/push", json=body, headers=monitor["headers"])
    assert r.status_code == 200, r.text
    return r.json()


def pull(client, monitor, cursor=None, reference_version=None):
    r = client.get(
        "/api/v1/sync/pull",
        params={"device_id": monitor["device_id"], "cursor": cursor, "reference_version": reference_version},
        headers=monitor["headers"],
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_push_applies_and_computes_follow_up(client, geo, monitor):
    e = make_error(geo)
    res = push(client, monitor, errors=[e])
    assert res["applied"] == 1
    receipt = res["receipts"][0]
    assert receipt["result"] == "applied"
    assert receipt["version"] == 1
    due = datetime.fromisoformat(receipt["next_follow_up_at"])
    last = datetime.fromisoformat(e["last_action_at"])
    assert due >= last + timedelta(hours=4)


def test_push_is_idempotent(client, geo, monitor):
    e = make_error(geo)
    push(client, monitor, errors=[e])
    res = push(client, monitor, errors=[e])
    assert res["duplicates"] == 1 and res["applied"] == 0


def test_newer_update_wins_and_bumps_version(client, geo, monitor):
    e = make_error(geo)
    push(client, monitor, errors=[e])
    e2 = dict(e, status="RESOLVED", client_updated_at=(datetime.now(timezone.utc)).isoformat(), resolved_at=datetime.now(timezone.utc).isoformat())
    res = push(client, monitor, errors=[e2])
    r = res["receipts"][0]
    assert r["result"] == "applied" and r["version"] == 2 and r["next_follow_up_at"] is None
    # An older copy arriving later is a duplicate, not a downgrade.
    res = push(client, monitor, errors=[e])
    assert res["receipts"][0]["result"] == "duplicate"
    pulled = pull(client, monitor)
    assert pulled["errors"][0]["status"] == "RESOLVED"


def test_follow_up_and_activity_append_only(client, geo, monitor):
    e = make_error(geo)
    fu = {"id": str(uuid.uuid4()), "error_id": e["id"], "at": datetime.now(timezone.utc).isoformat(), "method": "ONSITE", "contacted": "Mohamed Kamara", "outcome": "Agreed", "lat": 8.5, "lng": -13.2, "accuracy_m": 10, "gps_at": datetime.now(timezone.utc).isoformat(), "client_created_at": datetime.now(timezone.utc).isoformat()}
    act = {"id": str(uuid.uuid4()), "error_id": e["id"], "previous_status": None, "new_status": "UNRESOLVED", "action_taken": "Logged", "client_at": e["client_created_at"]}
    res = push(client, monitor, errors=[e], follow_ups=[fu], activity=[act])
    assert res["applied"] == 3
    res = push(client, monitor, follow_ups=[fu], activity=[act])
    assert res["duplicates"] == 2
    pulled = pull(client, monitor)
    rec = pulled["errors"][0]
    assert len(rec["follow_ups"]) == 1 and len(rec["activity"]) == 1


def test_out_of_scope_district_rejected(client, geo, monitor):
    e = make_error(geo, district="WAR", team="WAR-SA01")
    res = push(client, monitor, errors=[e])
    assert res["rejected"] == 1
    assert res["receipts"][0]["reason"] == "NOT_IN_SCOPE"


def test_pull_cursor_and_reference(client, geo, monitor):
    first = pull(client, monitor)
    assert first["reference"] is not None
    assert len(first["reference"]["districts"]) == 1  # scoped to WAU
    assert first["reference"]["districts"][0]["code"] == "WAU"
    assert len(first["reference"]["categories"]) == 10
    second = pull(client, monitor, reference_version=first["reference_version"])
    assert second["reference"] is None

    push(client, monitor, errors=[make_error(geo)])
    changed = pull(client, monitor, cursor=first["cursor"], reference_version=first["reference_version"])
    assert len(changed["errors"]) == 1
    nothing = pull(client, monitor, cursor=changed["cursor"], reference_version=first["reference_version"])
    assert nothing["errors"] == []


def test_second_tablet_restores_everything(client, geo, monitor):
    push(client, monitor, errors=[make_error(geo), make_error(geo)])
    new_device = str(uuid.uuid4())
    data = login(client, "fm.wau", "Password123", new_device)
    headers = auth(data["access_token"])
    client.post("/api/v1/devices/register", json={"device_id": new_device}, headers=headers)
    r = client.get("/api/v1/sync/pull", params={"device_id": new_device}, headers=headers)
    assert len(r.json()["errors"]) == 2


def test_blocked_device_rejected(client, admin, geo, monitor):
    r = client.patch(f"/api/v1/admin/devices/{monitor['device_id']}", json={"status": "BLOCKED"}, headers=admin)
    assert r.status_code == 200
    r = client.post("/api/v1/sync/push", json={"device_id": monitor["device_id"], "errors": [make_error(geo)]}, headers=monitor["headers"])
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "DEVICE_BLOCKED"


def test_batch_limit(client, geo, monitor):
    r = client.post("/api/v1/sync/push", json={"device_id": monitor["device_id"], "errors": [make_error(geo) for _ in range(201)]}, headers=monitor["headers"])
    assert r.status_code == 413
