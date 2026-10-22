"""Enumerator-to-EA links for EAs imported before the frame import recorded them.

The district frame workbooks (ENUMERATION_AREA sheet) name the enumerator of every EA. A compact copy of
that mapping ships with the server (app/data/ea_enumerators.json: {SA code: {EA code: enumerator code}}),
and at start-up every EA still without an enumerator is linked to the enumerator of its SA that carries
that code. Idempotent and cheap: only EAs with no link are looked at, and a marker setting remembers the
data version already applied. A later frame import overrides these links row by row.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Enumerator, EnumerationArea, Setting, Team

log = logging.getLogger(__name__)
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "ea_enumerators.json"
MARKER = "ea_enumerator_links"
VERSION = "frames-2026-09-11"


def load_mapping(path: Path = DATA_FILE) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def apply_links(db: Session, mapping: dict[str, dict[str, str]], only_missing: bool = True) -> dict:
    """Set EnumerationArea.enumerator_id from the mapping. Returns counts."""
    counts = {"linked": 0, "no_enumerator": 0, "not_in_mapping": 0, "already": 0}
    if not mapping:
        return counts
    teams = {t.id: t.code for t in db.execute(select(Team.id, Team.code)).all()}
    enums: dict[tuple[int, str], int] = {}
    for e in db.execute(select(Enumerator.id, Enumerator.team_id, Enumerator.code)).all():
        if e.code:
            enums.setdefault((e.team_id, str(e.code).strip()), e.id)
    q = select(EnumerationArea)
    if only_missing:
        q = q.where(EnumerationArea.enumerator_id.is_(None))
    for ea in db.execute(q).scalars():
        code = mapping.get(teams.get(ea.team_id, ""), {}).get(ea.code)
        if code is None:
            counts["not_in_mapping"] += 1
            continue
        enum_id = enums.get((ea.team_id, code))
        if enum_id is None:
            counts["no_enumerator"] += 1
            continue
        if ea.enumerator_id == enum_id:
            counts["already"] += 1
            continue
        ea.enumerator_id = enum_id
        counts["linked"] += 1
    db.flush()
    return counts


def ensure_links(db: Session) -> dict | None:
    """Start-up hook: apply the shipped mapping once per data version."""
    marker = db.get(Setting, MARKER)
    if marker is not None and marker.value == VERSION:
        return None
    counts = apply_links(db, load_mapping())
    if marker is None:
        db.add(Setting(key=MARKER, value=VERSION))
    else:
        marker.value = VERSION
    db.commit()
    log.info("EA-enumerator links %s: %s", VERSION, counts)
    return counts
