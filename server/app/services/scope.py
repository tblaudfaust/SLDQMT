"""Row-level scoping: which districts a user may see."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import District, Team, User, UserScope
from app.models.user import UNSCOPED_ROLES, Role


def assigned_district_ids_for(db: Session, user: User) -> list[int]:
    """The districts of the SAs that carry this officer's staff code (empty when no SA does)."""
    column = _workload_column(user)
    if column is None:
        return []
    rows = db.execute(select(Team.district_id).where(column == user.staff_code, Team.active.is_(True)).distinct()).scalars().all()
    return sorted(set(rows))


def district_ids_for(db: Session, user: User) -> list[int] | None:
    """None means every district. An empty list means nothing at all.
    A Field Monitor or District DQM whose staff code is on SAs in the workload is scoped to the
    district(s) of those SAs: the workload is the source of truth, so an account created with the
    wrong district still sees its own cases. Other accounts use their explicit scopes."""
    if user.role in UNSCOPED_ROLES:
        return None
    assigned = assigned_district_ids_for(db, user)
    if assigned:
        return assigned
    scopes = db.execute(select(UserScope).where(UserScope.user_id == user.id)).scalars().all()
    district_ids: set[int] = {s.district_id for s in scopes if s.district_id}
    region_ids = {s.region_id for s in scopes if s.region_id}
    if region_ids:
        rows = db.execute(select(District.id).where(District.region_id.in_(region_ids))).scalars().all()
        district_ids.update(rows)
    return sorted(district_ids)


def intersect(scope: list[int] | None, requested: list[int] | None) -> list[int] | None:
    """Narrow a scope by a requested filter; None on either side means no narrowing."""
    if scope is None:
        return requested
    if requested is None:
        return scope
    return sorted(set(scope) & set(requested))


def is_field_monitor(user: User) -> bool:
    return user.role == Role.FIELD_MONITOR


def _workload_column(user: User):
    if not user.staff_code:
        return None
    if user.role == Role.FIELD_MONITOR:
        return Team.monitor_code
    if user.role == Role.DISTRICT_DQM:
        return Team.dqm_code
    return None


def assigned_team_ids_for(db: Session, user: User) -> list[int] | None:
    """The SAs this officer is responsible for: teams whose monitor_code (Field Monitor) or
    dqm_code (District DQM) equals the account's staff code. None when the account has no
    staff code, or no SA carries it yet, so the district scope applies instead."""
    column = _workload_column(user)
    if column is None:
        return None
    ids = db.execute(select(Team.id).where(column == user.staff_code, Team.active.is_(True))).scalars().all()
    return sorted(ids) or None

