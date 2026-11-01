"""One-time resets of the live system before the ToT class practice (requested 2026-11-01), each run once at
start-up on the production server (a marker Setting per reset) with its counts written to the audit log:

* Field Monitor reset (`fm_reset_version`, audit `fm.reset`): every error record with its follow-ups and activity,
  the sync logs, the Field Monitors' registered tablets, the FM / DQM codes on every SA (the workload) and every
  Field Monitor account.
* Data Quality reset (`dqm_reset_version`, audit `dqm.reset`): every daily DQM report, every field exit check-out,
  the District DQM accounts and their tablets. Regional and National DQM accounts stay.

Reference frames, settings, rights, M&E data and every other account are kept; the audit trail is kept with the
removed accounts' rows unlinked. By hand: python -m scripts.reset_field_monitoring --yes [--dqm]
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models import Activity, AuditLog, Device, DqmDailyReport, ErrorRecord, ExitCheckout, FollowUp, RefreshToken, Role, Setting, SyncLog, Team, User, UserPermission, UserScope

log = logging.getLogger(__name__)

FM_MARKER, FM_VERSION = "fm_reset_version", "tot-practice-2026-11-01"
DQM_MARKER, DQM_VERSION = "dqm_reset_version", "tot-practice-2026-11-01"
# tables whose rows are removed by a reset: a user referenced only from these can be deleted
ACCOUNT_TABLES = {"device", "refresh_token", "user_scope", "user_permission"}


def _count(db: Session, model) -> int:
    return db.execute(select(func.count()).select_from(model)).scalar_one()


def _remove_accounts(db: Session, role: Role, counts: dict, cleared_tables: set[str], key: str) -> None:
    """Delete every account of `role` with its tablets, tokens, scopes and overrides; unlink it from every other
    table whose column allows NULL; keep an account still required by a NOT NULL column elsewhere."""
    ids = db.execute(select(User.id).where(User.role == role)).scalars().all()
    counts["devices"] = db.execute(select(func.count()).select_from(Device).where(Device.user_id.in_(ids))).scalar_one() if ids else 0
    if not ids:
        counts[key] = 0
        return
    db.execute(delete(Device).where(Device.user_id.in_(ids)))
    for model in (RefreshToken, UserScope, UserPermission):
        db.execute(delete(model).where(model.user_id.in_(ids)))
    blocked: set[int] = set()
    for table in Base.metadata.sorted_tables:
        if table.name in ACCOUNT_TABLES or table.name in cleared_tables or table.name == "user":
            continue
        for col in table.columns:
            if not any(fk.column.table.name == "user" for fk in col.foreign_keys):
                continue
            if col.nullable:
                db.execute(update(table).where(col.in_(ids)).values({col.name: None}))
            else:
                blocked.update(db.execute(select(col).where(col.in_(ids)).distinct()).scalars().all())
    removable = [i for i in ids if i not in blocked]
    counts["accounts_kept_with_other_records"] = db.execute(select(User.username).where(User.id.in_(blocked))).scalars().all() if blocked else []
    if removable:
        db.execute(delete(User).where(User.id.in_(removable)))
    counts[key] = len(removable)


def reset_field_monitoring(db: Session) -> dict:
    """Delete the operational data of the Field Monitor system, clear the workload and remove the FM accounts."""
    counts: dict = {}
    for model in (FollowUp, Activity, ErrorRecord, SyncLog):
        counts[model.__tablename__] = _count(db, model)
        db.execute(delete(model))
    _remove_accounts(db, Role.FIELD_MONITOR, counts, {"error", "follow_up", "activity", "sync_log"}, "field_monitor_accounts")
    counts["workload_sas_cleared"] = db.execute(select(func.count()).select_from(Team).where((Team.monitor_code.is_not(None)) | (Team.dqm_code.is_not(None)))).scalar_one()
    db.execute(update(Team).values(monitor_code=None, dqm_code=None))
    db.flush()
    return counts


def reset_data_quality(db: Session) -> dict:
    """Delete every daily DQM report and field exit check-out and remove the District DQM accounts."""
    counts: dict = {}
    for model in (DqmDailyReport, ExitCheckout):
        counts[model.__tablename__] = _count(db, model)
        db.execute(delete(model))
    _remove_accounts(db, Role.DISTRICT_DQM, counts, {"dqm_daily_report", "exit_checkout"}, "district_dqm_accounts")
    db.flush()
    return counts


def _run_once(db: Session, marker_key: str, version: str, action: str, fn) -> dict | None:
    marker = db.get(Setting, marker_key)
    if marker is not None and marker.value == version:
        return None
    counts = fn(db)
    if marker is None:
        db.add(Setting(key=marker_key, value=version))
    else:
        marker.value = version
    db.add(AuditLog(at=datetime.now(timezone.utc), user_id=None, action=action, entity="system", entity_id=None, detail=json.dumps({"version": version, **counts})))
    db.commit()
    log.warning("%s %s: %s", action, version, counts)
    return counts


def ensure_fm_reset(db: Session) -> dict | None:
    """Start-up hook: on the production server, run each reset once (never on a development or test database)."""
    if settings.ENVIRONMENT != "production":
        return None
    fm = _run_once(db, FM_MARKER, FM_VERSION, "fm.reset", reset_field_monitoring)
    dqm = _run_once(db, DQM_MARKER, DQM_VERSION, "dqm.reset", reset_data_quality)
    return None if fm is None and dqm is None else {"fm": fm, "dqm": dqm}
