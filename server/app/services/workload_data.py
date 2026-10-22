"""The workload distribution shipped with the server: which Field Monitor and DQM officer is responsible
for each SA (app/data/workload.json: {SA code: {"fm": "FM-41-001", "dqm": "DQM-41-001"}}).

Built from "Main-Workload-Distribution-DQM-FM.xlsx" (one sheet per district, one row per EA with the
SUPERVISOR ID, translated to the SA code through the district frames). Applied once per data version at
start-up: every SA in the file gets its officers; an SA of a covered district that the file no longer
lists loses its codes. The tablets concerned refresh their SA lists at the next sync.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.districts import canonical_staff_code
from app.models import Setting, Team

log = logging.getLogger(__name__)
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "workload.json"
MARKER = "workload_version"
VERSION = "main-distribution-2026-10-22"


def load_mapping(path: Path = DATA_FILE) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def apply_workload(db: Session, mapping: dict[str, dict[str, str]]) -> dict:
    """Set Team.monitor_code / dqm_code from the mapping. Returns counts."""
    counts = {"assigned": 0, "unchanged": 0, "cleared": 0, "unknown_sa": 0}
    if not mapping:
        return counts
    teams = db.execute(select(Team)).scalars().all()
    by_code = {t.code: t for t in teams}
    covered_districts = {by_code[sa].district_id for sa in mapping if sa in by_code}
    for sa, who in mapping.items():
        t = by_code.get(sa)
        if t is None:
            counts["unknown_sa"] += 1
            continue
        fm, dqm = canonical_staff_code(who.get("fm")), canonical_staff_code(who.get("dqm"))
        if t.monitor_code == fm and t.dqm_code == dqm:
            counts["unchanged"] += 1
        else:
            t.monitor_code, t.dqm_code = fm, dqm
            counts["assigned"] += 1
    for t in teams:
        if t.district_id in covered_districts and t.code not in mapping and (t.monitor_code or t.dqm_code):
            t.monitor_code, t.dqm_code = None, None
            counts["cleared"] += 1
    db.flush()
    return counts


def ensure_workload(db: Session) -> dict | None:
    """Start-up hook: apply the shipped distribution once per data version."""
    marker = db.get(Setting, MARKER)
    if marker is not None and marker.value == VERSION:
        return None
    mapping = load_mapping()
    if not mapping:
        return None
    counts = apply_workload(db, mapping)
    if marker is None:
        db.add(Setting(key=MARKER, value=VERSION))
    else:
        marker.value = VERSION
    db.commit()
    log.info("Workload %s applied: %s", VERSION, counts)
    return counts
