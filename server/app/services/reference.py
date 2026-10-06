"""Reference lists for tablets: scoped to the user's districts, with a
version string so an unchanged bundle is not re-sent."""

import hashlib

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    DEFAULT_SETTINGS,
    District,
    Enumerator,
    EnumerationArea,
    ErrorCategory,
    ErrorSource,
    Region,
    Setting,
    Supervisor,
    Team,
    User,
)
from app.schemas.reference import (
    DistrictOut,
    EAOut,
    EnumeratorOut,
    PickListOut,
    ReferenceBundle,
    RegionOut,
    SupervisorOut,
    TeamOut,
)
from app.services.scope import assigned_team_ids_for, district_ids_for

_TABLES = (Region, District, Team, Supervisor, Enumerator, EnumerationArea, ErrorCategory, ErrorSource, Setting)


def current_settings(db: Session) -> dict[str, str]:
    rows = {s.key: s.value for s in db.query(Setting).all()}
    return {**DEFAULT_SETTINGS, **rows}


def reference_version(db: Session, district_ids: list[int] | None, team_ids: list[int] | None = None) -> str:
    parts: list[str] = []
    for model in _TABLES:
        count, latest = db.execute(select(func.count(), func.max(model.updated_at))).one()
        parts.append(f"{model.__tablename__}:{count}:{latest}")
    parts.append("scope:" + ",".join(map(str, district_ids)) if district_ids is not None else "scope:all")
    parts.append("teams:" + ",".join(map(str, team_ids)) if team_ids is not None else "teams:all")
    parts.append("teams:" + ",".join(map(str, team_ids)) if team_ids is not None else "teams:all")
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def build_bundle(db: Session, user: User) -> ReferenceBundle:
    district_ids = district_ids_for(db, user)
    districts_q = select(District)
    if district_ids is not None:
        districts_q = districts_q.where(District.id.in_(district_ids))
    districts = db.execute(districts_q.order_by(District.name)).scalars().all()
    region_ids = {d.region_id for d in districts}
    regions_q = select(Region).order_by(Region.name)
    if district_ids is not None:
        regions_q = regions_q.where(Region.id.in_(region_ids)) if region_ids else regions_q.where(False)
    regions = db.execute(regions_q).scalars().all()

    teams_q = select(Team).where(Team.active.is_(True))
    if district_ids is not None:
        teams_q = teams_q.where(Team.district_id.in_(district_ids))
    # A Field Monitor with a workload gets only their own SAs (and those SAs' supervisors,
    # enumerators and EAs): a small bundle that syncs quickly and works offline.
    assigned = assigned_team_ids_for(db, user)
    if assigned is not None:
        teams_q = teams_q.where(Team.id.in_(assigned))
    # A Field Monitor with a workload gets only their own SAs (and those SAs' supervisors,
    # enumerators and EAs): a small bundle that syncs quickly and works offline.
    assigned = assigned_team_ids_for(db, user)
    if assigned is not None:
        teams_q = teams_q.where(Team.id.in_(assigned))
    teams = db.execute(teams_q.order_by(Team.code)).scalars().all()
    team_ids = [t.id for t in teams]

    def by_team(model):
        if not team_ids:
            return []
        return db.execute(select(model).where(model.team_id.in_(team_ids), model.active.is_(True))).scalars().all()

    return ReferenceBundle(
        version=reference_version(db, district_ids, assigned),
        regions=[RegionOut.model_validate(r) for r in regions],
        districts=[DistrictOut.model_validate(d) for d in districts],
        teams=[TeamOut.model_validate(t) for t in teams],
        supervisors=[SupervisorOut.model_validate(s) for s in by_team(Supervisor)],
        enumerators=[EnumeratorOut.model_validate(e) for e in by_team(Enumerator)],
        eas=[EAOut.model_validate(e) for e in by_team(EnumerationArea)],
        categories=[
            PickListOut.model_validate(c)
            for c in db.execute(select(ErrorCategory).order_by(ErrorCategory.sort_order, ErrorCategory.name)).scalars()
        ],
        sources=[
            PickListOut.model_validate(s)
            for s in db.execute(select(ErrorSource).order_by(ErrorSource.sort_order, ErrorSource.name)).scalars()
        ],
        settings=current_settings(db),
    )
