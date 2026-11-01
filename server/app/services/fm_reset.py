"""One-time reset of the Field Monitor error follow-up system (requested 2026-11-01, before the ToT class practice):
every error record with its follow-ups and activity, the sync logs, the Field Monitors' registered tablets, the
FM / DQM codes on every SA (the workload) and every Field Monitor account. Reference frames, settings, rights, the
daily DQM reports, exit check-outs, M&E data and every other account are kept; the audit trail is kept with the
removed accounts' rows unlinked.

Runs once at start-up on the production server (marker Setting `fm_reset_version`) and writes its counts as an
audit entry `fm.reset`; or by hand: python -m scripts.reset_field_monitoring --yes
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.models import Activity, AuditLog, Device, ErrorRecord, FollowUp, RefreshToken, Role, Setting, SyncLog, Team, User, UserPermission, UserScope

log = logging.getLogger(__name__)

MARKER = "fm_reset_version"
VERSION = "tot-practice-2026-11-01"
OWN_TABLES = {"error", "follow_up", "activity", "sync_log", "device", "refresh_token", "user_scope", "user_permission"}


def _count(db: Session, model) -> int:
    return db.execute(select(func.count()).select_from(model)).scalar_one()


def reset_field_monitoring(db: Session) -> dict:
    """Delete the operational data of the Field Monitor system, clear the workload and remove the FM accounts."""
    counts: dict[str, int | list] = {}
    for model in (FollowUp, Activity, ErrorRecord, SyncLog):
        counts[model.__tablename__] = _count(db, model)
        db.execute(delete(model))

    fm_ids = db.execute(select(User.id).where(User.role == Role.FIELD_MONITOR)).scalars().all()
    counts["devices"] = db.execute(select(func.count()).select_from(Device).where(Device.user_id.in_(fm_ids))).scalar_one() if fm_ids else 0
    if fm_ids:
        db.execute(delete(Device).where(Device.user_id.in_(fm_ids)))
        for model in (RefreshToken, UserScope, UserPermission):
            db.execute(delete(model).where(model.user_id.in_(fm_ids)))
        # every other table that points at a user: unlink where the column allows it, otherwise keep the account
        blocked: set[int] = set()
        for table in Base.metadata.sorted_tables:
            if table.name in OWN_TABLES or table.name == "user":
                continue
            for col in table.columns:
                if not any(fk.column.table.name == "user" for fk in col.foreign_keys):
                    continue
                if col.nullable:
                    db.execute(update(table).where(col.in_(fm_ids)).values({col.name: None}))
                else:
                    blocked.update(db.execute(select(col).where(col.in_(fm_ids)).distinct()).scalars().all())
        removable = [i for i in fm_ids if i not in blocked]
        kept = db.execute(select(User.username).where(User.id.in_(blocked))).scalars().all() if blocked else []
        if removable:
            db.execute(delete(User).where(User.id.in_(removable)))
        counts["field_monitor_accounts"] = len(removable)
        counts["accounts_kept_with_other_records"] = kept
    else:
        counts["field_monitor_accounts"] = 0

    counts["workload_sas_cleared"] = db.execute(select(func.count()).select_from(Team).where((Team.monitor_code.is_not(None)) | (Team.dqm_code.is_not(None)))).scalar_one()
    db.execute(update(Team).values(monitor_code=None, dqm_code=None))
    db.flush()
    return counts


def ensure_fm_reset(db: Session) -> dict | None:
    """Start-up hook: on the production server, run the reset once (never on a development or test database)."""
    if settings.ENVIRONMENT != "production":
        return None
    marker = db.get(Setting, MARKER)
    if marker is not None and marker.value == VERSION:
        return None
    counts = reset_field_monitoring(db)
    if marker is None:
        db.add(Setting(key=MARKER, value=VERSION))
    else:
        marker.value = VERSION
    db.add(AuditLog(at=datetime.now(timezone.utc), user_id=None, action="fm.reset", entity="system", entity_id=None,
                    detail=json.dumps({"version": VERSION, **counts})))
    db.commit()
    log.warning("Field Monitor reset %s: %s", VERSION, counts)
    return counts
