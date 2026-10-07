"""Row-level scoping: which districts a user may see."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import District, Team, User, UserScope
from app.models.user import UNSCOPED_ROLES, Role


def district_ids_for(db: Session, user: User) -> list[int] | None:
    """None means every district. An empty list means nothing at all."""
    if user.role in UNSCOPED_ROLES:
        return None
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


def assigned_team_ids_for(db: Session, user: User) -> list[int] | None:
    """The SAs this officer is responsible for: teams whose monitor_code (Field Monitor) or
    dqm_code (District DQM) equals the account's staff code. None when the account has no
    staff code, or no SA carries it yet, so the district scope applies instead."""
    if not user.staff_code:
        return None
    if user.role == Role.FIELD_MONITOR:
        column = Team.monitor_code
    elif user.role == Role.DISTRICT_DQM:
        column = Team.dqm_code
    else:
        return None
    ids = db.execute(select(Team.id).where(column == user.staff_code, Team.active.is_(True))).scalars().all()
    return sorted(ids) or None

