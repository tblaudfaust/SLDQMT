"""ToT class practice set: the practice workload and the DQM / Field Monitor practice accounts.

The regional ToT training (25 halls, 1,363 participants) practises on the live system. Each hall seat is a
practice officer: workload pairs DQM-<venue>-H<hall>-<n> / FM-<venue>-H<hall>-<n> share the same SAs. The
workbook `app/data/practice/tot_practice_workload.xlsx` (FIELD_MONITOR sheet: one row per SA with the DQM ID and
Field monitor ID) is shipped with the server; an administrator loads it from Admin → Reference, typing the two
shared practice passwords. Loading:

* assigns the practice codes to the SAs (the same import as a workload frame upload, so re-loading is safe);
* creates one account per practice code: username = code, staff code = code (so the officer's scope is exactly
  the SAs of the workload), role from the prefix, district scope = the districts of its SAs, the shared password
  of its role, no forced password change (the password is shared on purpose for the class), active now.

Removing the set afterwards deletes the practice accounts (with tablets, tokens, scopes and overrides) and clears
the practice codes from the SAs; records they created are kept with the account unlinked, as the resets do.
"""

from __future__ import annotations

import re
from collections import OrderedDict, defaultdict
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Device, District, RefreshToken, Role, Team, User, UserPermission, UserScope
from app.services.import_service import import_reference

WORKBOOK = Path(__file__).resolve().parent.parent / "data" / "practice" / "tot_practice_workload.xlsx"
# Start-up load on the production server (requested 2026-11-02): the set is loaded once, with the two shared class
# passwords given by Statistics Sierra Leone, stored here only as bcrypt hashes (the plain passwords are handed to the
# halls on the printed login sheets). Remove the set from Admin -> Reference after the training.
MARKER, VERSION = "tot_practice_version", "tot-practice-2026-11-02"
PRACTICE_HASHES = {
    "DISTRICT_DQM": "$2b$12$9gh0vFXZhkyoAmqfFRjGQeJkBSnU6C/AiHbtE8HB.7qD18C5oOkCC",
    "FIELD_MONITOR": "$2b$12$NywcoFuGDn8sExcC.z8LxO6gWcGtDSRatr.77dJrPQBAsc1TMBUDy",
}
CODE = re.compile(r"^(DQM|FM)-([A-Z]{2,4})-H(\d{1,2})-(\d{1,3})$")
VENUES = {"WAU": "Western Area Urban", "WAR": "Western Area Rural", "PLO": "Port Loko", "BO": "Bo", "BOM": "Makeni", "KEN": "Kenema"}
PRACTICE_USERNAME = User.username.like("dqm-%-h%-%") | User.username.like("fm-%-h%-%")
PRACTICE_TEAM = Team.monitor_code.like("FM-%-H%-%") | Team.dqm_code.like("DQM-%-H%-%")


def is_practice_code(code: str | None) -> bool:
    return bool(code and CODE.match(code.strip().upper()))


def full_name(code: str) -> str:
    m = CODE.match(code)
    if not m:
        return code
    kind, venue, hall, n = m.groups()
    return f"{'DQM' if kind == 'DQM' else 'Field Monitor'} {VENUES.get(venue, venue)} hall {int(hall)} seat {int(n)}"


def read_officers(path: Path | str | None = None) -> "OrderedDict[str, set[str]]":
    """{practice code: {district codes of its SAs}} from the FIELD_MONITOR sheet, in sheet order."""
    wb = load_workbook(path or WORKBOOK, read_only=True, data_only=True)
    ws = wb["FIELD_MONITOR"] if "FIELD_MONITOR" in wb.sheetnames else wb.active
    rows = ws.iter_rows(values_only=True)
    header = [str(h or "").strip().lower() for h in next(rows)]
    col = {name: i for i, name in enumerate(header)}
    dist, dqm, fm = col["dist_code"], col["dqm id"], col["field monitor id"]
    officers: "OrderedDict[str, set[str]]" = OrderedDict()
    for r in rows:
        if not r or r[dist] is None:
            continue
        d = str(r[dist]).strip()
        for i in (dqm, fm):
            code = str(r[i] or "").strip().upper()
            if code:
                officers.setdefault(code, set()).add(d)
    return officers


def status(db: Session) -> dict:
    users = db.execute(select(User.role, func.count()).where(PRACTICE_USERNAME).group_by(User.role)).all()
    by_role = {str(getattr(r, "value", r)): n for r, n in users}
    return {
        "loaded": bool(by_role),
        "dqm_accounts": by_role.get("DISTRICT_DQM", 0),
        "fm_accounts": by_role.get("FIELD_MONITOR", 0),
        "sas_assigned": db.execute(select(func.count()).select_from(Team).where(PRACTICE_TEAM)).scalar_one(),
        "logged_in": db.execute(select(func.count()).select_from(User).where(PRACTICE_USERNAME, User.last_login_at.is_not(None))).scalar_one(),
        "workbook": WORKBOOK.name if WORKBOOK.exists() else None,
    }


def load(db: Session, dqm_password: str | None = None, fm_password: str | None = None, reset_passwords: bool = False,
         path: Path | str | None = None, hashes: dict[str, str] | None = None) -> dict:
    """Assign the practice workload and create (or, with reset_passwords, re-password) the practice accounts.
    Passwords come either in clear (typed by the administrator) or as ready bcrypt hashes per role."""
    path = Path(path) if path else WORKBOOK   # resolved at call time so tests can point WORKBOOK elsewhere
    if hashes is None:
        hashes = {"DISTRICT_DQM": hash_password(dqm_password or ""), "FIELD_MONITOR": hash_password(fm_password or "")}
    result = import_reference(db, path.name, path)
    officers = read_officers(path)
    districts = {d.code: d for d in db.execute(select(District)).scalars()}
    existing = {u.username: u for u in db.execute(select(User).where(PRACTICE_USERNAME)).scalars()}
    created = updated = 0
    missing: set[str] = set()
    for code, dcodes in officers.items():
        role = Role.DISTRICT_DQM if code.startswith("DQM-") else Role.FIELD_MONITOR
        user = existing.get(code.lower())
        if user is None:
            user = User(username=code.lower(), password_hash=hashes[role.value], full_name=full_name(code), role=role,
                        staff_code=code, active=True, must_change_password=False)
            db.add(user)
            db.flush()
            created += 1
        else:
            user.staff_code, user.role, user.active, user.must_change_password = code, role, True, False
            if reset_passwords:
                user.password_hash = hashes[role.value]
            updated += 1
        have = {s.district_id for s in user.scopes}
        for dc in sorted(dcodes):
            d = districts.get(dc)
            if d is None:
                missing.add(dc)
                continue
            if d.id not in have:
                user.scopes.append(UserScope(district_id=d.id))
    db.flush()
    return {
        "sas_assigned": result.assigned, "rows": result.rows, "warnings": result.warnings[:10],
        "accounts_created": created, "accounts_updated": updated,
        "dqm_accounts": sum(1 for c in officers if c.startswith("DQM-")), "fm_accounts": sum(1 for c in officers if c.startswith("FM-")),
        "unknown_districts": sorted(missing), "passwords_reset": reset_passwords,
    }


def ensure_practice_loaded(db: Session) -> dict | None:
    """Start-up hook: on the production server, load the practice set once (marker Setting), like the resets."""
    import json
    import logging
    from datetime import datetime, timezone

    from app.core.config import settings
    from app.models import AuditLog, Setting

    if settings.ENVIRONMENT != "production" or not WORKBOOK.exists():
        return None
    marker = db.get(Setting, MARKER)
    if marker is not None and marker.value == VERSION:
        return None
    counts = load(db, hashes=PRACTICE_HASHES)
    if marker is None:
        db.add(Setting(key=MARKER, value=VERSION))
    else:
        marker.value = VERSION
    db.add(AuditLog(at=datetime.now(timezone.utc), user_id=None, action="practice.load", entity="system", entity_id=None,
                    detail=json.dumps({"version": VERSION, **{k: v for k, v in counts.items() if k != "warnings"}})))
    db.commit()
    logging.getLogger(__name__).warning("practice.load %s: %s", VERSION, {k: v for k, v in counts.items() if k != "warnings"})
    return counts


def remove(db: Session) -> dict:
    """Delete the practice accounts and clear the practice codes from the SAs; other tables keep their rows unlinked."""
    from app.db.base import Base

    ids = db.execute(select(User.id).where(PRACTICE_USERNAME)).scalars().all()
    counts = {"accounts": len(ids), "devices": 0}
    if ids:
        counts["devices"] = db.execute(select(func.count()).select_from(Device).where(Device.user_id.in_(ids))).scalar_one()
        for model in (Device, RefreshToken, UserScope, UserPermission):
            db.execute(delete(model).where(model.user_id.in_(ids)))
        blocked: set[int] = set()
        for table in Base.metadata.sorted_tables:
            if table.name in {"device", "refresh_token", "user_scope", "user_permission", "user"}:
                continue
            for col in table.columns:
                if not any(fk.column.table.name == "user" for fk in col.foreign_keys):
                    continue
                if col.nullable:
                    db.execute(update(table).where(col.in_(ids)).values({col.name: None}))
                else:
                    blocked.update(db.execute(select(col).where(col.in_(ids)).distinct()).scalars().all())
        removable = [i for i in ids if i not in blocked]
        if removable:
            db.execute(delete(User).where(User.id.in_(removable)))
        counts["accounts"] = len(removable)
        counts["accounts_kept_with_other_records"] = len(blocked)
    counts["sas_cleared"] = db.execute(select(func.count()).select_from(Team).where(PRACTICE_TEAM)).scalar_one()
    db.execute(update(Team).where(Team.monitor_code.like("FM-%-H%-%")).values(monitor_code=None))
    db.execute(update(Team).where(Team.dqm_code.like("DQM-%-H%-%")).values(dqm_code=None))
    db.flush()
    return counts
