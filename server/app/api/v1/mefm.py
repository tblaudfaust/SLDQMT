"""M&E Field Monitoring (stage 1): the frame in the signed-in user's scope and the frame version history."""

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_perm
from app.db.session import get_db
from app.models import District, EnumerationArea, MefmChiefdom, MefmFrameVersion, MefmSection, Region, Team, User
from app.services.scope import district_ids_for

router = APIRouter(prefix="/mefm", tags=["me-field-monitoring"])
view = require_perm("mefm.view")


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
