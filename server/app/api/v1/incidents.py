"""Census Incident Log: reporting and handling (accounts with the incidents rights), the dashboard, SA codes,
exports, and the public page where supervisors report with their SA code."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import audit, require_perm
from app.core import incidents as spec
from app.db.session import get_db
from app.models import District, User
from app.schemas.incident import ActionIn, Dashboard, IncidentEdit, IncidentIn, IncidentOut, PersonOut, PublicIncidentIn, PublicIncidentOut, PublicTrackOut, SaCodeImportOut, SaCodeIn, SaCodeOut
from app.services import incident_service as svc
from app.services import report_service

router = APIRouter(tags=["incidents"])
view = require_perm("incidents.view")
report_perm = require_perm("incidents.report")
manage = require_perm("incidents.manage")
export_perm = require_perm("incidents.export")
settings_perm = require_perm("incidents.settings")


def _filters(district_id: int | None = None, region_id: int | None = None, status: str | None = Query(default=None, max_length=16), severity: str | None = Query(default=None, max_length=16),
             category: str | None = Query(default=None, max_length=32), phase: str | None = Query(default=None, max_length=16), level: str | None = Query(default=None, max_length=16),
             owner_id: int | None = None, team_id: int | None = None, overdue: bool = False, date_from: date | None = None, date_to: date | None = None, search: str | None = Query(default=None, max_length=100)) -> dict:
    return {"district_id": district_id, "region_id": region_id, "status": status or None, "severity": severity or None, "category": category or None, "phase": phase or None, "level": level or None,
            "owner_id": owner_id, "team_id": team_id, "overdue": overdue, "date_from": date_from, "date_to": date_to, "search": search or None}


@router.get("/incidents/spec")
def get_spec(_: User = Depends(view)):
    return spec.public_spec()


@router.get("/incidents/dashboard", response_model=Dashboard)
def dashboard(filters: dict = Depends(_filters), db: Session = Depends(get_db), user: User = Depends(view)):
    return svc.dashboard(db, user, filters)


@router.get("/incidents", response_model=list[IncidentOut])
def list_incidents(filters: dict = Depends(_filters), limit: int = Query(default=500, ge=1, le=5000), db: Session = Depends(get_db), user: User = Depends(view)):
    return svc.list_incidents(db, user, filters, limit)


@router.post("/incidents", response_model=IncidentOut, status_code=201)
def create(body: IncidentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(report_perm)):
    inc = svc.report(db, user, body)
    audit(db, user, "incident.report", "incident", inc.id, {"number": inc.number, "severity": inc.severity, "category": inc.category}, request)
    db.commit()
    return svc.to_out(svc.get(db, user, inc.id), svc.Names(db, [inc]), with_updates=True)


@router.get("/incidents/people", response_model=list[PersonOut])
def people(district_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(view)):
    return svc.people(db, user, district_id)


@router.get("/incidents/open-for-team/{team_id}", response_model=list[IncidentOut])
def open_for_team(team_id: int, db: Session = Depends(get_db), user: User = Depends(view)):
    """Open incidents of a supervisory area: shown as a warning on the exit checkout (it never blocks)."""
    return svc.open_for_team(db, user, team_id)


@router.get("/incidents/sa-codes", response_model=list[SaCodeOut])
def sa_codes(db: Session = Depends(get_db), user: User = Depends(view)):
    return svc.sa_codes(db, user)


@router.put("/incidents/sa-codes", response_model=SaCodeImportOut)
def put_sa_codes(body: list[SaCodeIn], request: Request, db: Session = Depends(get_db), user: User = Depends(settings_perm)):
    out = svc.upsert_sa_codes(db, body)
    audit(db, user, "incident.sa_codes", "incident_sa_code", None, {"created": out.created, "updated": out.updated}, request)
    db.commit()
    return out


@router.post("/incidents/sa-codes/import", response_model=SaCodeImportOut)
async def import_sa_codes(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(settings_perm)):
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(413, "The file is larger than 5 MB")
    out = svc.upsert_sa_codes(db, svc.parse_sa_file(file.filename or "sa.csv", data))
    audit(db, user, "incident.sa_codes_import", "incident_sa_code", None, {"file": file.filename, "created": out.created, "updated": out.updated}, request)
    db.commit()
    return out


@router.get("/incidents/export")
def export(request: Request, format: str = Query(default="xlsx", pattern="^(xlsx|pdf)$"), filters: dict = Depends(_filters), db: Session = Depends(get_db), user: User = Depends(export_perm)):
    report = svc.export(db, user, filters)
    audit(db, user, "incident.export", "incident", None, {"format": format, **{k: str(v) for k, v in filters.items() if v}}, request)
    db.commit()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    if format == "pdf":
        return Response(report_service.to_pdf(report), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="incidents-{stamp}.pdf"'})
    return Response(report_service.to_xlsx(report), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="incidents-{stamp}.xlsx"'})


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: int, db: Session = Depends(get_db), user: User = Depends(view)):
    inc = svc.get(db, user, incident_id)
    return svc.to_out(inc, svc.Names(db, [inc]), with_updates=True)


@router.patch("/incidents/{incident_id}", response_model=IncidentOut)
def edit_incident(incident_id: int, body: IncidentEdit, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    inc = svc.edit(db, user, svc.get(db, user, incident_id), body)
    audit(db, user, "incident.edit", "incident", inc.id, body.model_dump(exclude_unset=True, mode="json"), request)
    db.commit()
    return svc.to_out(inc, svc.Names(db, [inc]), with_updates=True)


@router.post("/incidents/{incident_id}/actions", response_model=IncidentOut)
def act(incident_id: int, body: ActionIn, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    """acknowledge, assign, start, resolve, close, reject, reopen, escalate or comment."""
    inc = svc.act(db, user, svc.get(db, user, incident_id), body)
    audit(db, user, f"incident.{body.action}", "incident", inc.id, {"number": inc.number, "status": inc.status, "level": inc.level, "owner_id": inc.owner_id}, request)
    db.commit()
    return svc.to_out(inc, svc.Names(db, [inc]), with_updates=True)


@router.post("/incidents/{incident_id}/comments", response_model=IncidentOut)
def comment(incident_id: int, body: ActionIn, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    """Anyone who can see an incident may add a comment (the reporter following up, a viewer adding information)."""
    inc = svc.act(db, user, svc.get(db, user, incident_id), ActionIn(action="comment", text=body.text))
    db.commit()
    return svc.to_out(inc, svc.Names(db, [inc]), with_updates=True)


@router.delete("/incidents/{incident_id}", status_code=204)
def delete_incident(incident_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    inc = svc.get(db, user, incident_id)
    audit(db, user, "incident.delete", "incident", inc.id, {"number": inc.number}, request)
    svc.delete(db, inc)
    db.commit()
    return Response(status_code=204)


# ---- public page (supervisors, by SA code) ------------------------------------------------------------


@router.get("/public/incidents/spec")
def public_spec():
    return spec.public_spec()


@router.get("/public/incidents/sa/{sa_code}")
def public_sa(sa_code: str, db: Session = Depends(get_db)):
    """What the SA code resolves to, so the supervisor sees their district and SA before reporting."""
    if not spec.SA_CODE_RE.match(sa_code):
        raise HTTPException(400, "The SA code has 12 digits")
    row, team, district, recognised = svc._resolve_sa(db, sa_code)
    return {"sa_code": sa_code, "recognised": recognised, "district": district.name if district else None, "sa_name": (row.sa_name if row and row.sa_name else (team.name if team else None)), "team_code": team.code if team else None, "supervisor_name": row.supervisor_name if row else None}


@router.post("/public/incidents", response_model=PublicIncidentOut)
def public_report(body: PublicIncidentIn, db: Session = Depends(get_db)):
    inc, token = svc.public_report(db, body)
    db.commit()
    row, team, _district, _rec = svc._resolve_sa(db, (body.sa_code or "").strip() or None)
    district = db.get(District, inc.district_id) if inc.district_id else None
    return PublicIncidentOut(number=inc.number, track_token=token, district=district.name if district else None, sa_name=(row.sa_name if row and row.sa_name else (team.name if team else None)), sa_recognised=inc.sa_recognised, severity=inc.severity, status=inc.status)


@router.get("/public/incidents/{number}", response_model=PublicTrackOut)
def public_track(number: str, token: str = Query(min_length=8), db: Session = Depends(get_db)):
    return svc.public_track(db, number, token)
