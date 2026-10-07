"""M&E Field Monitoring: tablet sync (forms and check-ins) and the reads the dashboards use.

A pushed form is validated against the questionnaire spec, tied to an EA of the officer's
district by its 10-digit code, checked for GPS plausibility and saved with its issues log.
Push is idempotent on the tablet-generated id; an older copy of a form is a duplicate."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core import mefm_form
from app.core.config import settings
from app.models import (
    District,
    Enumerator,
    EnumerationArea,
    IssueStatus,
    MefmCheckin,
    MefmChiefdom,
    MefmIssue,
    MefmSection,
    MefmVisit,
    Region,
    Supervisor,
    SyncLog,
    Team,
    User,
    VisitStatus,
)
from app.schemas.mefm import (
    CheckinIn,
    FrameChiefdom,
    FrameDistrict,
    FrameEa,
    FrameSection,
    FrameTeam,
    IssueOut,
    MefmFrame,
    MefmPullResponse,
    MefmPushRequest,
    MefmPushResponse,
    MefmReceipt,
    VisitDetail,
    VisitIn,
    VisitRow,
    VisitState,
)
from app.services.reference import current_settings
from app.services.scope import district_ids_for
from app.services.sync_service import SyncError, get_active_device

FORM_VERSION = hashlib.sha1(json.dumps(mefm_form.public_spec(), sort_keys=True).encode()).hexdigest()[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class GpsPolicy:
    def __init__(self, conf: dict[str, str]):
        self.ea_distance_m = float(conf.get("mefm_ea_distance_m") or 1000)
        self.accuracy_m = float(conf.get("mefm_gps_accuracy_m") or 50)
        self.max_speed_kmh = float(conf.get("mefm_max_speed_kmh") or 120)
        self.night_start = mefm_form.parse_time(conf.get("mefm_night_start") or "20:00", datetime.strptime("20:00", "%H:%M").time())
        self.night_end = mefm_form.parse_time(conf.get("mefm_night_end") or "05:00", datetime.strptime("05:00", "%H:%M").time())


def _previous_point(db: Session, user: User, before: datetime | None, exclude_id: str | None):
    """The officer's latest earlier GPS point (visit or check-in), for the speed and repeat checks."""
    points: list[tuple[datetime, float, float]] = []
    q = select(MefmVisit.gps_at, MefmVisit.lat, MefmVisit.lng).where(MefmVisit.user_id == user.id, MefmVisit.deleted_at.is_(None), MefmVisit.gps_at.is_not(None))
    if exclude_id:
        q = q.where(MefmVisit.id != exclude_id)
    if before:
        q = q.where(MefmVisit.gps_at < before)
    row = db.execute(q.order_by(MefmVisit.gps_at.desc()).limit(1)).first()
    if row:
        points.append((_aware(row[0]), row[1], row[2]))
    q = select(MefmCheckin.at, MefmCheckin.lat, MefmCheckin.lng).where(MefmCheckin.user_id == user.id)
    if exclude_id:
        q = q.where(MefmCheckin.id != exclude_id)
    if before:
        q = q.where(MefmCheckin.at < before)
    row = db.execute(q.order_by(MefmCheckin.at.desc()).limit(1)).first()
    if row:
        points.append((_aware(row[0]), row[1], row[2]))
    return max(points, key=lambda p: p[0]) if points else None


def gps_flags(db: Session, user: User, policy: GpsPolicy, lat: float, lng: float, accuracy: float | None, at: datetime | None, exclude_id: str | None = None) -> list[str]:
    flags: list[str] = []
    if accuracy is not None and accuracy > policy.accuracy_m:
        flags.append("poor_accuracy")
    if at is not None and mefm_form.night(at.astimezone(timezone.utc).time(), policy.night_start, policy.night_end):
        flags.append("night")
    prev = _previous_point(db, user, at, exclude_id)
    if prev is not None:
        prev_at, plat, plng = prev
        if round(plat, 5) == round(lat, 5) and round(plng, 5) == round(lng, 5):
            flags.append("repeated_point")
        elif at is not None and prev_at is not None:
            hours = (at - prev_at).total_seconds() / 3600
            if hours > 0:
                speed = haversine_m(plat, plng, lat, lng) / 1000 / hours
                if speed > policy.max_speed_kmh:
                    flags.append("too_fast")
    return flags


def _ea_for(db: Session, code: str) -> EnumerationArea | None:
    digits = "".join(ch for ch in code if ch.isdigit())
    if not digits:
        return None
    return db.execute(select(EnumerationArea).where(EnumerationArea.pop_ea_code == digits, EnumerationArea.active.is_(True))).scalars().first()


def _apply_visit(db: Session, user: User, device, item: VisitIn, scope: list[int] | None, policy: GpsPolicy, app_version: str | None) -> MefmReceipt:
    existing = db.get(MefmVisit, item.id)
    if existing is not None and existing.user_id != user.id:
        return MefmReceipt(kind="visit", id=item.id, result="rejected", reason="NOT_OWNER")
    if existing is not None and existing.deleted_at is not None:
        return MefmReceipt(kind="visit", id=item.id, result="rejected", reason="DELETED")
    incoming = _aware(item.client_updated_at)
    if existing is not None and _aware(existing.client_updated_at) >= incoming:
        return MefmReceipt(kind="visit", id=item.id, result="duplicate", version=existing.version, flags=json.loads(existing.flags))

    ea = _ea_for(db, item.pop_ea_code)
    if ea is None:
        return MefmReceipt(kind="visit", id=item.id, result="rejected", reason="UNKNOWN_EA", errors=["A8: no EA with this 10-digit code in the frame"])
    team = db.get(Team, ea.team_id)
    if scope is not None and team.district_id not in scope:
        return MefmReceipt(kind="visit", id=item.id, result="rejected", reason="NOT_IN_SCOPE", errors=["A8: this EA is outside your district"])

    answers = dict(item.answers or {})
    answers["A8"] = ea.pop_ea_code
    answers["A15"] = {"lat": item.gps.lat, "lng": item.gps.lng, "accuracy_m": item.gps.accuracy_m, "at": item.gps.at.isoformat() if item.gps.at else ""}
    clean, errors = mefm_form.validate(answers)
    if errors:
        return MefmReceipt(kind="visit", id=item.id, result="rejected", reason="INVALID", errors=errors)
    gps_at = _aware(item.gps.at)
    flags = gps_flags(db, user, policy, item.gps.lat, item.gps.lng, item.gps.accuracy_m, gps_at, exclude_id=item.id)
    distance = None
    if ea.lat is not None and ea.lng is not None:
        distance = haversine_m(item.gps.lat, item.gps.lng, ea.lat, ea.lng)
        if distance > policy.ea_distance_m:
            flags.append("far_from_ea")
    chiefdom = db.execute(select(MefmChiefdom).where(MefmChiefdom.code == ea.chiefdom_code)).scalars().first() if ea.chiefdom_code else None
    section = db.execute(select(MefmSection).where(MefmSection.code == ea.section_code)).scalars().first() if ea.section_code else None
    auto_issues = mefm_form.critical_issues(clean)
    indicators = mefm_form.indicators(clean)

    if existing is None:
        visit = MefmVisit(id=item.id, user_id=user.id, client_created_at=_aware(item.client_created_at), version=1)
        db.add(visit)
    else:
        visit = existing
        visit.version += 1
    visit.device_id = device.id
    visit.district_id = team.district_id
    visit.chiefdom_id = chiefdom.id if chiefdom else None
    visit.section_id = section.id if section else None
    visit.team_id = team.id
    visit.ea_id = ea.id
    visit.pop_ea_code = ea.pop_ea_code
    visit.visit_date = date.fromisoformat(clean["A2"])
    visit.phase = clean["A12"]
    visit.visit_type = clean.get("A14")
    visit.arrived = clean.get("A3_arrived")
    visit.left = clean.get("A3_left")
    visit.team_found = clean.get("A16") == "1" if "A16" in clean else None
    visit.lat, visit.lng, visit.accuracy_m, visit.gps_at = item.gps.lat, item.gps.lng, item.gps.accuracy_m, gps_at
    visit.distance_to_ea_m = distance
    visit.flags = json.dumps(flags)
    visit.answers = json.dumps(clean)
    visit.indicators = json.dumps(indicators)
    visit.overall_rating = clean.get("J7")
    visit.app_version = app_version
    visit.client_updated_at = incoming
    visit.server_updated_at = _now()
    visit.status = VisitStatus.SUBMITTED
    db.flush()

    # Issues: re-create the open rows from this copy of the form; rows a reviewer has already
    # worked on (in progress or closed) are kept.
    for issue in list(visit.issues):
        if issue.status == IssueStatus.OPEN:
            db.delete(issue)
    db.flush()
    typed = clean.get("J_issues") or []
    rows = [dict(r, auto=False) for r in typed] + auto_issues
    for r in rows:
        db.add(MefmIssue(
            visit_id=visit.id, district_id=visit.district_id, question=r.get("question") or None, severity=r["severity"],
            description=r["description"] or "(no description)", action=r.get("action") or None, referred_to=r.get("referred_to") or None,
            deadline=date.fromisoformat(r["deadline"]) if r.get("deadline") else None, auto=bool(r.get("auto")),
        ))
    visit.critical_count = sum(1 for r in rows if r["severity"] == "Critical")
    db.flush()
    return MefmReceipt(kind="visit", id=item.id, result="applied", version=visit.version, flags=flags)


def _apply_checkin(db: Session, user: User, device, item: CheckinIn, scope: list[int] | None, policy: GpsPolicy) -> MefmReceipt:
    if db.get(MefmCheckin, item.id) is not None:
        return MefmReceipt(kind="checkin", id=item.id, result="duplicate")
    chiefdom = db.execute(select(MefmChiefdom).where(MefmChiefdom.code == item.chiefdom_code)).scalars().first() if item.chiefdom_code else None
    section = db.execute(select(MefmSection).where(MefmSection.code == item.section_code)).scalars().first() if item.section_code else None
    if section is not None and chiefdom is None:
        chiefdom = db.get(MefmChiefdom, section.chiefdom_id)
    if chiefdom is None:
        return MefmReceipt(kind="checkin", id=item.id, result="rejected", reason="UNKNOWN_CHIEFDOM")
    if scope is not None and chiefdom.district_id not in scope:
        return MefmReceipt(kind="checkin", id=item.id, result="rejected", reason="NOT_IN_SCOPE")
    at = _aware(item.at)
    flags = gps_flags(db, user, policy, item.gps.lat, item.gps.lng, item.gps.accuracy_m, at, exclude_id=item.id)
    db.add(MefmCheckin(
        id=item.id, user_id=user.id, device_id=device.id, district_id=chiefdom.district_id, chiefdom_id=chiefdom.id,
        section_id=section.id if section else None, note=item.note, lat=item.gps.lat, lng=item.gps.lng, accuracy_m=item.gps.accuracy_m,
        at=at, flags=json.dumps(flags),
    ))
    db.flush()
    return MefmReceipt(kind="checkin", id=item.id, result="applied", flags=flags)


def push(db: Session, user: User, req: MefmPushRequest) -> MefmPushResponse:
    if len(req.visits) + len(req.checkins) > settings.SYNC_BATCH_MAX:
        raise SyncError(413, "BATCH_TOO_LARGE", f"At most {settings.SYNC_BATCH_MAX} records per push")
    device = get_active_device(db, user, req.device_id)
    scope = district_ids_for(db, user)
    policy = GpsPolicy(current_settings(db))
    log = SyncLog(device_id=device.id, user_id=user.id)
    db.add(log)
    receipts: list[MefmReceipt] = []
    # oldest first so the speed check compares each point with the one before it
    for item in sorted(req.checkins, key=lambda c: c.at):
        receipts.append(_apply_checkin(db, user, device, item, scope, policy))
    for item in sorted(req.visits, key=lambda v: v.client_updated_at):
        receipts.append(_apply_visit(db, user, device, item, scope, policy, req.app_version))
    applied = sum(1 for r in receipts if r.result == "applied")
    duplicates = sum(1 for r in receipts if r.result == "duplicate")
    rejected = sum(1 for r in receipts if r.result == "rejected")
    device.last_sync_at = _now()
    device.pending_reported = max(req.pending_count - applied - duplicates, 0)
    if req.app_version:
        device.app_version = req.app_version
    log.pushed, log.rejected, log.finished_at = applied, rejected, _now()
    log.result = "OK" if rejected == 0 else "PARTIAL"
    db.commit()
    return MefmPushResponse(receipts=receipts, applied=applied, duplicates=duplicates, rejected=rejected, server_time=_now())


def frame_version(db: Session, scope: list[int] | None) -> str:
    parts = []
    for model in (District, MefmChiefdom, MefmSection, Team, Supervisor, Enumerator, EnumerationArea):
        count, latest = db.execute(select(func.count(), func.max(model.updated_at))).one()
        parts.append(f"{model.__tablename__}:{count}:{latest}")
    parts.append("scope:" + (",".join(map(str, scope)) if scope is not None else "all"))
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def build_frame(db: Session, scope: list[int] | None) -> MefmFrame:
    dq = select(District).order_by(District.name)
    if scope is not None:
        dq = dq.where(District.id.in_(scope))
    districts = db.execute(dq).scalars().all()
    ids = [d.id for d in districts]
    regions = {r.id: r.name for r in db.execute(select(Region)).scalars()}
    if not ids:
        return MefmFrame(version=frame_version(db, scope), districts=[], chiefdoms=[], sections=[], teams=[], eas=[])
    chiefdoms = db.execute(select(MefmChiefdom).where(MefmChiefdom.district_id.in_(ids), MefmChiefdom.active.is_(True)).order_by(MefmChiefdom.code)).scalars().all()
    sections = db.execute(select(MefmSection).where(MefmSection.district_id.in_(ids), MefmSection.active.is_(True)).order_by(MefmSection.code)).scalars().all()
    teams = db.execute(select(Team).where(Team.district_id.in_(ids), Team.active.is_(True)).order_by(Team.code)).scalars().all()
    team_ids = [t.id for t in teams]
    sup = {}
    for s in db.execute(select(Supervisor).where(Supervisor.team_id.in_(team_ids), Supervisor.active.is_(True))).scalars() if team_ids else []:
        sup.setdefault(s.team_id, s.name)
    enums: dict[int, list[str]] = {}
    for e in db.execute(select(Enumerator).where(Enumerator.team_id.in_(team_ids), Enumerator.active.is_(True)).order_by(Enumerator.name)).scalars() if team_ids else []:
        enums.setdefault(e.team_id, []).append(e.name)
    eas = db.execute(select(EnumerationArea).where(EnumerationArea.team_id.in_(team_ids), EnumerationArea.active.is_(True)).order_by(EnumerationArea.code)).scalars().all() if team_ids else []
    return MefmFrame(
        version=frame_version(db, scope),
        districts=[FrameDistrict(id=d.id, code=d.code, name=d.name, region=regions.get(d.region_id, "")) for d in districts],
        chiefdoms=[FrameChiefdom(id=c.id, district_id=c.district_id, code=c.code, name=c.name) for c in chiefdoms],
        sections=[FrameSection(id=s.id, district_id=s.district_id, chiefdom_id=s.chiefdom_id, code=s.code, name=s.name) for s in sections],
        teams=[FrameTeam(id=t.id, district_id=t.district_id, code=t.code, name=t.name, chiefdom=t.chiefdom, supervisor=sup.get(t.id), enumerators=enums.get(t.id, [])) for t in teams],
        eas=[FrameEa(id=e.id, team_id=e.team_id, code=e.code, name=e.name, locality=e.locality, pop_ea_code=e.pop_ea_code, chiefdom_code=e.chiefdom_code, section_code=e.section_code,
                     loc_status=e.loc_status, expected_households=e.expected_households if e.expected_households is not None else e.households, lat=e.lat, lng=e.lng) for e in eas],
    )


def _parse_cursor(cursor: str | None) -> datetime | None:
    if not cursor:
        return None
    try:
        return _aware(datetime.fromisoformat(cursor))
    except ValueError:
        raise SyncError(400, "BAD_CURSOR", "cursor must be an ISO-8601 timestamp")


def pull(db: Session, user: User, device_id: str, cursor: str | None, frame_ver: str | None, form_ver: str | None, limit: int = 500) -> MefmPullResponse:
    device = get_active_device(db, user, device_id)
    since = _parse_cursor(cursor)
    q = select(MefmVisit).options(selectinload(MefmVisit.issues)).where(MefmVisit.user_id == user.id).order_by(MefmVisit.server_updated_at, MefmVisit.id)
    if since is not None:
        q = q.where(MefmVisit.server_updated_at > since)
    rows = db.execute(q.limit(limit + 1)).scalars().all()
    more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = max(_aware(r.server_updated_at) for r in rows).isoformat() if rows else (cursor or _now().isoformat())
    scope = district_ids_for(db, user)
    current = frame_version(db, scope)
    frame = build_frame(db, scope) if frame_ver != current else None
    device.last_sync_at = _now()
    db.commit()
    return MefmPullResponse(
        cursor=next_cursor,
        form=mefm_form.public_spec() if form_ver != FORM_VERSION else None,
        form_version=FORM_VERSION,
        frame=frame,
        frame_version=current,
        settings=current_settings(db),
        visits=[VisitState(id=r.id, status=r.status.value, version=r.version, flags=json.loads(r.flags), review_note=r.review_note,
                           open_issues=sum(1 for i in r.issues if i.status != IssueStatus.CLOSED), server_updated_at=r.server_updated_at, deleted=r.deleted_at is not None) for r in rows],
        server_time=_now(),
        more=more,
        pin_reset=user.pin_reset_requested_at is not None,
    )


# ---- reads ----------------------------------------------------------------------------------------

def _row(db: Session, v: MefmVisit, names: dict) -> dict:
    return dict(
        id=v.id, user_id=v.user_id, officer=names["users"].get(v.user_id, ""), district_id=v.district_id, district=names["districts"].get(v.district_id, ""),
        chiefdom=names["chiefdoms"].get(v.chiefdom_id), section=names["sections"].get(v.section_id), sa_code=names["teams"].get(v.team_id),
        pop_ea_code=v.pop_ea_code, ea_name=names["eas"].get(v.ea_id), visit_date=v.visit_date, phase=v.phase, visit_type=v.visit_type, team_found=v.team_found,
        overall_rating=v.overall_rating, critical_count=v.critical_count, open_issues=sum(1 for i in v.issues if i.status != IssueStatus.CLOSED),
        flags=json.loads(v.flags), distance_to_ea_m=v.distance_to_ea_m, lat=v.lat, lng=v.lng, status=v.status.value, server_updated_at=v.server_updated_at,
    )


def _names(db: Session, visits: list[MefmVisit]) -> dict:
    def lookup(model, ids, attr="name"):
        ids = {i for i in ids if i is not None}
        if not ids:
            return {}
        return {r.id: getattr(r, attr) for r in db.execute(select(model).where(model.id.in_(ids))).scalars()}

    return {
        "users": lookup(User, [v.user_id for v in visits], "full_name"),
        "districts": lookup(District, [v.district_id for v in visits]),
        "chiefdoms": lookup(MefmChiefdom, [v.chiefdom_id for v in visits]),
        "sections": lookup(MefmSection, [v.section_id for v in visits]),
        "teams": lookup(Team, [v.team_id for v in visits], "code"),
        "eas": lookup(EnumerationArea, [v.ea_id for v in visits]),
    }


def list_visits(db: Session, user: User, district_id: int | None = None, date_from: date | None = None, date_to: date | None = None, phase: str | None = None, officer_id: int | None = None, limit: int = 500) -> list[VisitRow]:
    scope = district_ids_for(db, user)
    q = select(MefmVisit).options(selectinload(MefmVisit.issues)).where(MefmVisit.deleted_at.is_(None))
    if scope is not None:
        q = q.where(MefmVisit.district_id.in_(scope))
    if district_id is not None:
        q = q.where(MefmVisit.district_id == district_id)
    if date_from:
        q = q.where(MefmVisit.visit_date >= date_from)
    if date_to:
        q = q.where(MefmVisit.visit_date <= date_to)
    if phase:
        q = q.where(MefmVisit.phase == phase)
    if officer_id is not None:
        q = q.where(MefmVisit.user_id == officer_id)
    visits = db.execute(q.order_by(MefmVisit.visit_date.desc(), MefmVisit.server_updated_at.desc()).limit(limit)).scalars().all()
    names = _names(db, visits)
    return [VisitRow(**_row(db, v, names)) for v in visits]


def get_visit(db: Session, user: User, visit_id: str) -> VisitDetail | None:
    v = db.execute(select(MefmVisit).options(selectinload(MefmVisit.issues)).where(MefmVisit.id == visit_id, MefmVisit.deleted_at.is_(None))).scalars().first()
    if v is None:
        return None
    scope = district_ids_for(db, user)
    if scope is not None and v.district_id not in scope:
        return None
    names = _names(db, [v])
    return VisitDetail(**_row(db, v, names), answers=json.loads(v.answers), indicators=json.loads(v.indicators), issues=[IssueOut.model_validate(i) for i in v.issues],
                       accuracy_m=v.accuracy_m, gps_at=v.gps_at, review_note=v.review_note, reviewed_at=v.reviewed_at, client_created_at=v.client_created_at)
