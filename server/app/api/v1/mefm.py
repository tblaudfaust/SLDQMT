"""M&E Field Monitoring: the frame in scope (stage 1), the questionnaire, tablet sync and visit reads (stage 2)."""

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.core import mefm_form
from app.db.session import get_db
from app.models import District, EnumerationArea, MefmChiefdom, MefmFrameVersion, MefmSection, Region, Team, User
from app.schemas.mefm import MefmPullResponse, MefmPushRequest, MefmPushResponse, VisitDetail, VisitRow
from app.services import mefm_service
from app.services.scope import district_ids_for
from app.services.sync_service import SyncError

router = APIRouter(prefix="/mefm", tags=["me-field-monitoring"])
view = require_perm("mefm.view")
collect = require_perm("mefm.collect", "sync.use")


class DistrictFrame(BaseModel):
    district_id: int
    district: str
    region: str
    chiefdoms: int
    sections: int
    sas: int
    eas: int
    eas_with_point: int


class Overview(BaseModel):
    """Counts from the frame, limited to the districts the user may see (the access rule in action)."""

    scope: str  # "national", "region", or the district names
    districts: list[DistrictFrame]
    totals: dict[str, int]
    frame_version: dict | None = None


@router.get("/overview", response_model=Overview)
def overview(db: Session = Depends(get_db), user: User = Depends(view)):
    scope = district_ids_for(db, user)
    q = select(District).order_by(District.name)
    if scope is not None:
        q = q.where(District.id.in_(scope))
    districts = db.execute(q).scalars().all()
    regions = {r.id: r.name for r in db.execute(select(Region)).scalars()}
    ids = [d.id for d in districts]

    def count_by_district(stmt):
        return dict(db.execute(stmt).all())

    chief = count_by_district(select(MefmChiefdom.district_id, func.count()).where(MefmChiefdom.district_id.in_(ids), MefmChiefdom.active.is_(True)).group_by(MefmChiefdom.district_id)) if ids else {}
    sect = count_by_district(select(MefmSection.district_id, func.count()).where(MefmSection.district_id.in_(ids), MefmSection.active.is_(True)).group_by(MefmSection.district_id)) if ids else {}
    sas = count_by_district(select(Team.district_id, func.count()).where(Team.district_id.in_(ids), Team.active.is_(True)).group_by(Team.district_id)) if ids else {}
    eas = count_by_district(select(Team.district_id, func.count()).select_from(EnumerationArea).join(Team, Team.id == EnumerationArea.team_id).where(Team.district_id.in_(ids), EnumerationArea.active.is_(True)).group_by(Team.district_id)) if ids else {}
    pts = count_by_district(select(Team.district_id, func.count()).select_from(EnumerationArea).join(Team, Team.id == EnumerationArea.team_id).where(Team.district_id.in_(ids), EnumerationArea.active.is_(True), EnumerationArea.lat.is_not(None)).group_by(Team.district_id)) if ids else {}
    rows = [
        DistrictFrame(district_id=d.id, district=d.name, region=regions.get(d.region_id, ""), chiefdoms=chief.get(d.id, 0), sections=sect.get(d.id, 0), sas=sas.get(d.id, 0), eas=eas.get(d.id, 0), eas_with_point=pts.get(d.id, 0))
        for d in districts
    ]
    totals = {k: sum(getattr(r, k) for r in rows) for k in ("chiefdoms", "sections", "sas", "eas", "eas_with_point")}
    totals["districts"] = len(rows)
    if scope is None:
        label = "national"
    elif len({d.region_id for d in districts}) == 1 and len(districts) > 1:
        label = f"region: {regions.get(districts[0].region_id, '')}"
    else:
        label = ", ".join(d.name for d in districts) or "no district assigned"
    latest = db.execute(select(MefmFrameVersion).order_by(MefmFrameVersion.id.desc())).scalars().first()
    fv = {"id": latest.id, "filename": latest.filename, "applied_at": latest.created_at.isoformat(), "rows": latest.rows, "counts": json.loads(latest.counts)} if latest else None
    return Overview(scope=label, districts=rows, totals=totals, frame_version=fv)


def _raise(e: SyncError):
    raise HTTPException(e.status_code, {"code": e.code, "detail": e.detail})


@router.get("/form")
def form(_: User = Depends(view)):
    """The questionnaire as data (sections, items, codes, skips), with its version."""
    return {"version": mefm_service.FORM_VERSION, **mefm_form.public_spec()}


@router.post("/sync/push", response_model=MefmPushResponse)
def sync_push(body: MefmPushRequest, db: Session = Depends(get_db), user: User = Depends(collect)):
    """Forms and check-ins from the tablet. Each record is validated and answered with a receipt;
    a form the server already holds in the same or a newer version is a duplicate."""
    try:
        return mefm_service.push(db, user, body)
    except SyncError as e:
        db.rollback()
        _raise(e)


@router.get("/sync/pull", response_model=MefmPullResponse)
def sync_pull(
    device_id: str = Query(min_length=1, max_length=36),
    cursor: str | None = None,
    frame_version: str | None = None,
    form_version: str | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(collect),
):
    """The district frame, the questionnaire and the state of the officer's own forms."""
    try:
        return mefm_service.pull(db, user, device_id, cursor, frame_version, form_version, limit)
    except SyncError as e:
        _raise(e)


@router.get("/visits", response_model=list[VisitRow])
def visits(
    district_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    phase: str | None = None,
    officer_id: int | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
    user: User = Depends(view),
):
    return mefm_service.list_visits(db, user, district_id, date_from, date_to, phase, officer_id, limit)


@router.get("/visits/{visit_id}", response_model=VisitDetail)
def visit(visit_id: str, db: Session = Depends(get_db), user: User = Depends(view)):
    v = mefm_service.get_visit(db, user, visit_id)
    if v is None:
        raise HTTPException(404, "Visit not found")
    return v
