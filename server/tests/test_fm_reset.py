"""One-time reset of the Field Monitor system: records, sync logs, tablets, workload codes and FM accounts go;
reference data, other accounts, their records and the audit trail stay; the start-up hook runs only in production, once."""

from datetime import date, datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.db import session as session_module
from app.models import AuditLog, Device, District, ErrorCategory, ErrorRecord, ErrorStatus, Region, Role, Setting, SupportMethod, Team, User
from app.services import fm_reset
from tests.conftest import auth, login


def test_reset_removes_records_workload_and_fm_accounts(client, admin, monkeypatch):
    for u, role in (("fm.one", "FIELD_MONITOR"), ("fm.two", "FIELD_MONITOR"), ("dqm.one", "DISTRICT_DQM")):
        assert client.post("/api/v1/admin/users", json={"username": u, "password": "Password123", "full_name": u, "role": role}, headers=admin).status_code == 201
    login(client, "fm.one", "Password123", device_id="11111111-1111-1111-1111-111111111111")  # a refresh token for the FM account
    db = session_module.SessionLocal()
    try:
        region = Region(code="9", name="Test"); db.add(region); db.flush()
        district = District(region_id=region.id, code="99", name="Testland"); db.add(district); db.flush()
        db.add_all([Team(district_id=district.id, code="99901001", name="SA 1", monitor_code="FM-Tst-001", dqm_code="DQM-Tst-001"),
                    Team(district_id=district.id, code="99901002", name="SA 2", monitor_code="FM-Tst-002", dqm_code="DQM-Tst-002"),
                    Team(district_id=district.id, code="99901003", name="SA 3")])
        fm = db.execute(select(User).where(User.username == "fm.one")).scalar_one()
        dqm = db.execute(select(User).where(User.username == "dqm.one")).scalar_one()
        cat = db.execute(select(ErrorCategory)).scalars().first()
        now = datetime.now(timezone.utc)
        db.add(Device(id="11111111-1111-1111-1111-111111111111", user_id=fm.id, model="Tab"))
        db.add(ErrorRecord(id="e1", display_id="E-1", user_id=fm.id, district_id=district.id, category_id=cat.id, description="x", date_received=date.today(),
                           support_method=SupportMethod.REMOTE, status=ErrorStatus.UNRESOLVED, last_action_at=now, client_created_at=now, client_updated_at=now))
        db.add(AuditLog(at=now, user_id=fm.id, action="auth.login"))
        db.commit()
        dqm_id, fm_id = dqm.id, fm.id
    finally:
        db.close()

    # outside production the hook does nothing
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    db = session_module.SessionLocal()
    try:
        assert fm_reset.ensure_fm_reset(db) is None
        assert db.get(Setting, fm_reset.MARKER) is None and db.execute(select(ErrorRecord)).scalars().first() is not None
        monkeypatch.setattr(settings, "ENVIRONMENT", "production")
        counts = fm_reset.ensure_fm_reset(db)
        assert counts["error"] == 1 and counts["devices"] == 1 and counts["field_monitor_accounts"] == 2 and counts["workload_sas_cleared"] == 2
        assert counts["accounts_kept_with_other_records"] == []
        assert db.execute(select(ErrorRecord)).scalars().first() is None and db.execute(select(Device)).scalars().first() is None
        assert all(t.monitor_code is None and t.dqm_code is None for t in db.execute(select(Team)).scalars().all())
        assert {u.username for u in db.execute(select(User)).scalars().all()} >= {"dqm.one", "admin"} and db.execute(select(User).where(User.role == Role.FIELD_MONITOR)).scalars().first() is None
        assert db.get(User, dqm_id) is not None
        assert db.execute(select(AuditLog).where(AuditLog.user_id == fm_id)).scalars().first() is None  # unlinked...
        assert db.execute(select(AuditLog).where(AuditLog.action == "auth.login", AuditLog.user_id.is_(None))).scalars().first() is not None  # ...but kept
        done = db.execute(select(AuditLog).where(AuditLog.action == "fm.reset")).scalar_one()
        assert '"field_monitor_accounts": 2' in done.detail and db.get(Setting, fm_reset.MARKER).value == fm_reset.VERSION
        # a second start-up does not run it again
        assert fm_reset.ensure_fm_reset(db) is None
    finally:
        db.close()
    # the reference lists survive and the DQM account still signs in
    assert client.get("/api/v1/admin/reference/districts", headers=auth(login(client, "dqm.one", "Password123")["access_token"])).status_code == 200
    assert client.post("/api/v1/auth/login", json={"username": "fm.one", "password": "Password123"}).status_code == 401
