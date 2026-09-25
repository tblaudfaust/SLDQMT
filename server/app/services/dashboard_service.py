"""Aggregates behind the web dashboard and the reports. Every query starts
from `base_query`, which applies the user's scope and the shared filter set."""

from datetime import date, datetime, timedelta, timezone
from statistics import median

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models import (
    Device,
    District,
    Enumerator,
    EnumerationArea,
    ErrorCategory,
    ErrorRecord,
    ErrorStatus,
    FollowUp,
    Supervisor,
    Team,
    User,
)
from app.schemas.dashboard import (
    AgeingBand,
    Bucket,
    ErrorListRow,
    Filters,
    MonitorRow,
    OverdueRow,
    Summary,
    TeamRow,
    TrendPoint,
)
from app.services.scope import district_ids_for, intersect


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def overdue_clause(now: datetime):
    return and_(ErrorRecord.status == ErrorStatus.UNRESOLVED, ErrorRecord.next_follow_up_at < now)


def base_query(db: Session, user: User, f: Filters, now: datetime | None = None, include_deleted: bool = False) -> Select:
    now = now or _now()
    scope = intersect(district_ids_for(db, user), f.district_id)
    q = select(ErrorRecord)
    if not include_deleted:
        q = q.where(ErrorRecord.deleted_at.is_(None))
    if scope is not None:
        q = q.where(ErrorRecord.district_id.in_(scope))
    if f.team_id:
        q = q.where(ErrorRecord.team_id == f.team_id)
    if f.ea_id:
        q = q.where(ErrorRecord.ea_id == f.ea_id)
    if f.category_id:
        q = q.where(ErrorRecord.category_id == f.category_id)
    if f.status:
        q = q.where(ErrorRecord.status == f.status)
    if f.date_from:
        q = q.where(ErrorRecord.date_received >= f.date_from)
    if f.date_to:
        q = q.where(ErrorRecord.date_received <= f.date_to)
    if f.supervisor_id:
        q = q.where(ErrorRecord.supervisor_id == f.supervisor_id)
    if f.supervisor:
        q = q.where(ErrorRecord.supervisor_name.ilike(f"%{f.supervisor}%"))
    if f.enumerator:
        q = q.where(ErrorRecord.enumerator_name.ilike(f"%{f.enumerator}%"))
    if f.user_id:
        q = q.where(ErrorRecord.user_id == f.user_id)
    if f.support_method:
        q = q.where(ErrorRecord.support_method == f.support_method)
    if f.overdue_only:
        q = q.where(overdue_clause(now))
    if f.search:
        like = f"%{f.search}%"
        q = q.where(
            or_(
                ErrorRecord.display_id.ilike(like),
                ErrorRecord.description.ilike(like),
                ErrorRecord.supervisor_name.ilike(like),
                ErrorRecord.enumerator_name.ilike(like),
                ErrorRecord.action_taken.ilike(like),
            )
        )
    return q


def _rows(db: Session, user: User, f: Filters) -> list[ErrorRecord]:
    return db.execute(base_query(db, user, f)).scalars().all()


def summary(db: Session, user: User, f: Filters) -> Summary:
    now = _now()
    rows = _rows(db, user, f)
    total = len(rows)
    resolved = [r for r in rows if r.status == ErrorStatus.RESOLVED]
    unresolved = total - len(resolved)
    overdue = sum(1 for r in rows if r.status == ErrorStatus.UNRESOLVED and _aware(r.next_follow_up_at) and _aware(r.next_follow_up_at) < now)
    days = [
        (_aware(r.resolved_at) - datetime.combine(r.date_received, datetime.min.time(), tzinfo=timezone.utc)).total_seconds() / 86400
        for r in resolved
        if r.resolved_at
    ]
    last_sync = db.execute(select(func.max(Device.last_sync_at))).scalar()
    return Summary(
        total=total,
        resolved=len(resolved),
        unresolved=unresolved,
        overdue=overdue,
        resolution_rate=round(len(resolved) / total * 100, 1) if total else 0.0,
        median_days_to_resolve=round(median(days), 1) if days else None,
        as_of=now,
        last_sync_at=_aware(last_sync),
    )


def _bucketize(rows: list[ErrorRecord], key_fn, label_fn, now: datetime) -> list[Bucket]:
    buckets: dict = {}
    for r in rows:
        k = key_fn(r)
        b = buckets.setdefault(k, {"total": 0, "resolved": 0, "unresolved": 0, "overdue": 0})
        b["total"] += 1
        if r.status == ErrorStatus.RESOLVED:
            b["resolved"] += 1
        else:
            b["unresolved"] += 1
            if _aware(r.next_follow_up_at) and _aware(r.next_follow_up_at) < now:
                b["overdue"] += 1
    out = [Bucket(key=k, label=label_fn(k), **v) for k, v in buckets.items()]
    return sorted(out, key=lambda b: (-b.total, b.label))


def by_district(db: Session, user: User, f: Filters) -> list[Bucket]:
    rows = _rows(db, user, f)
    names = {d.id: d.name for d in db.execute(select(District)).scalars()}
    return _bucketize(rows, lambda r: r.district_id, lambda k: names.get(k, str(k)), _now())


def by_category(db: Session, user: User, f: Filters) -> list[Bucket]:
    rows = _rows(db, user, f)
    names = {c.id: c.name for c in db.execute(select(ErrorCategory)).scalars()}
    return _bucketize(rows, lambda r: r.category_id, lambda k: names.get(k, str(k)), _now())


def trend(db: Session, user: User, f: Filters, granularity: str = "day") -> list[TrendPoint]:
    rows = _rows(db, user, f)
    received: dict[str, int] = {}
    resolved: dict[str, int] = {}

    def key_of(d: date) -> str:
        if granularity == "week":
            iso = d.isocalendar()
            return f"{iso.year}-W{iso.week:02d}"
        return d.isoformat()

    for r in rows:
        received[key_of(r.date_received)] = received.get(key_of(r.date_received), 0) + 1
        if r.resolved_at:
            k = key_of(_aware(r.resolved_at).date())
            resolved[k] = resolved.get(k, 0) + 1
    keys = sorted(set(received) | set(resolved))
    return [TrendPoint(period=k, received=received.get(k, 0), resolved=resolved.get(k, 0)) for k in keys]


AGE_BANDS = (("0-2 days", 0, 2), ("3-7 days", 3, 7), ("8-14 days", 8, 14), ("15+ days", 15, 10**6))


def ageing(db: Session, user: User, f: Filters) -> list[AgeingBand]:
    today = _now().date()
    rows = [r for r in _rows(db, user, f) if r.status == ErrorStatus.UNRESOLVED]
    counts = {name: 0 for name, _, _ in AGE_BANDS}
    for r in rows:
        age = (today - r.date_received).days
        for name, lo, hi in AGE_BANDS:
            if lo <= age <= hi:
                counts[name] += 1
                break
    return [AgeingBand(band=name, count=counts[name]) for name, _, _ in AGE_BANDS]


def by_monitor(db: Session, user: User, f: Filters) -> list[MonitorRow]:
    now = _now()
    rows = _rows(db, user, f)
    per_user: dict[int, dict] = {}
    for r in rows:
        b = per_user.setdefault(r.user_id, {"total": 0, "unresolved": 0, "overdue": 0, "last_activity": None})
        b["total"] += 1
        if r.status == ErrorStatus.UNRESOLVED:
            b["unresolved"] += 1
            if _aware(r.next_follow_up_at) and _aware(r.next_follow_up_at) < now:
                b["overdue"] += 1
        la = _aware(r.last_action_at)
        if b["last_activity"] is None or (la and la > b["last_activity"]):
            b["last_activity"] = la
    # Include monitors with zero errors so "never synced" is visible.
    scope = district_ids_for(db, user)
    monitors_q = select(User).where(User.role == "FIELD_MONITOR", User.active.is_(True))
    monitors = db.execute(monitors_q).scalars().all()
    district_names = {d.id: d.name for d in db.execute(select(District)).scalars()}
    out: list[MonitorRow] = []
    for m in monitors:
        m_districts = [s.district_id for s in m.scopes if s.district_id]
        if scope is not None and not (set(m_districts) & set(scope)) and m.id not in per_user:
            continue
        dev = db.execute(
            select(Device).where(Device.user_id == m.id).order_by(Device.last_sync_at.desc().nullslast())
        ).scalars().first()
        b = per_user.get(m.id, {"total": 0, "unresolved": 0, "overdue": 0, "last_activity": None})
        out.append(
            MonitorRow(
                user_id=m.id,
                full_name=m.full_name,
                districts=", ".join(district_names.get(d, str(d)) for d in m_districts),
                total=b["total"],
                unresolved=b["unresolved"],
                overdue=b["overdue"],
                last_sync_at=_aware(dev.last_sync_at) if dev else None,
                last_activity_at=b["last_activity"],
                app_version=dev.app_version if dev else None,
                pending_reported=dev.pending_reported if dev else 0,
            )
        )
    return sorted(out, key=lambda r: (-r.overdue, -r.unresolved, r.full_name))


def by_team(db: Session, user: User, f: Filters) -> list[TeamRow]:
    now = _now()
    rows = _rows(db, user, f)
    teams = {t.id: t for t in db.execute(select(Team)).scalars()}
    districts = {d.id: d.name for d in db.execute(select(District)).scalars()}
    supervisors: dict[int, str] = {}
    for s in db.execute(select(Supervisor).where(Supervisor.active.is_(True))).scalars():
        supervisors.setdefault(s.team_id, s.name)
    per_team: dict = {}
    for r in rows:
        b = per_team.setdefault(r.team_id, {"total": 0, "resolved": 0, "unresolved": 0, "overdue": 0, "district": r.district_id})
        b["total"] += 1
        if r.status == ErrorStatus.RESOLVED:
            b["resolved"] += 1
        else:
            b["unresolved"] += 1
            if _aware(r.next_follow_up_at) and _aware(r.next_follow_up_at) < now:
                b["overdue"] += 1
    out = []
    for team_id, b in per_team.items():
        t = teams.get(team_id)
        out.append(
            TeamRow(
                team_id=team_id,
                team=f"{t.code} {t.name}" if t else "No team",
                district=districts.get(b["district"], ""),
                supervisor=supervisors.get(team_id) if team_id else None,
                total=b["total"],
                resolved=b["resolved"],
                unresolved=b["unresolved"],
                overdue=b["overdue"],
            )
        )
    return sorted(out, key=lambda r: (-r.overdue, -r.unresolved, r.team))


def overdue_list(db: Session, user: User, f: Filters) -> list[OverdueRow]:
    now = _now()
    f2 = f.model_copy(update={"overdue_only": True})
    rows = db.execute(base_query(db, user, f2, now).order_by(ErrorRecord.next_follow_up_at)).scalars().all()
    districts = {d.id: d.name for d in db.execute(select(District)).scalars()}
    teams = {t.id: f"{t.code} {t.name}" for t in db.execute(select(Team)).scalars()}
    cats = {c.id: c.name for c in db.execute(select(ErrorCategory)).scalars()}
    users = {u.id: u.full_name for u in db.execute(select(User)).scalars()}
    return [
        OverdueRow(
            id=r.id,
            display_id=r.display_id,
            district=districts.get(r.district_id, ""),
            team=teams.get(r.team_id) if r.team_id else None,
            category=cats.get(r.category_id, ""),
            supervisor_name=r.supervisor_name,
            monitor=users.get(r.user_id, ""),
            next_follow_up_at=_aware(r.next_follow_up_at),
            hours_overdue=round((now - _aware(r.next_follow_up_at)).total_seconds() / 3600, 1),
        )
        for r in rows
    ]


def error_list(db: Session, user: User, f: Filters, page: int, page_size: int, deleted_only: bool = False) -> tuple[list[ErrorListRow], int]:
    now = _now()
    q = base_query(db, user, f, now, include_deleted=deleted_only)
    if deleted_only:
        q = q.where(ErrorRecord.deleted_at.is_not(None))
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = (
        db.execute(q.order_by(ErrorRecord.last_action_at.desc()).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    ids = [r.id for r in rows]
    fu_counts: dict[str, int] = {}
    if ids:
        for error_id, n in db.execute(
            select(FollowUp.error_id, func.count()).where(FollowUp.error_id.in_(ids)).group_by(FollowUp.error_id)
        ):
            fu_counts[error_id] = n
    districts = {d.id: d.name for d in db.execute(select(District)).scalars()}
    teams = {t.id: f"{t.code} {t.name}" for t in db.execute(select(Team)).scalars()}
    eas = {e.id: e.code for e in db.execute(select(EnumerationArea)).scalars()}
    cats = {c.id: c.name for c in db.execute(select(ErrorCategory)).scalars()}
    users = {u.id: u.full_name for u in db.execute(select(User)).scalars()}
    out = [
        ErrorListRow(
            id=r.id,
            display_id=r.display_id,
            district=districts.get(r.district_id, ""),
            team=teams.get(r.team_id) if r.team_id else None,
            ea=eas.get(r.ea_id) if r.ea_id else None,
            category=cats.get(r.category_id, ""),
            supervisor_name=r.supervisor_name,
            enumerator_name=r.enumerator_name,
            description=r.description,
            date_received=r.date_received,
            support_method=r.support_method,
            status=r.status,
            next_follow_up_at=_aware(r.next_follow_up_at),
            overdue=bool(r.status == ErrorStatus.UNRESOLVED and _aware(r.next_follow_up_at) and _aware(r.next_follow_up_at) < now),
            monitor=users.get(r.user_id, ""),
            last_action_at=_aware(r.last_action_at),
            follow_up_count=fu_counts.get(r.id, 0),
        )
        for r in rows
    ]
    return out, total
