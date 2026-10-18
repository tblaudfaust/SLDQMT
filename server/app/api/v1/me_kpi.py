"""M&E Field Tool (KPIs): the form spec and geography the field app caches, offline-safe sync of reports,
the register, the dashboard summary and exports. Scoped by the officer's districts."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import audit, require_perm
from app.core import me_kpi_form
from app.db.session import get_db
from app.models import User
from app.schemas.me_kpi import GeoBundle, ReportIn, ReportOut, Summary, SyncIn, SyncOut
from app.services import me_kpi_service as svc
from app.services import report_service

router = APIRouter(tags=["me-kpi"])
view = require_perm("me_kpi.view")
collect = require_perm("me_kpi.collect")
manage = require_perm("me_kpi.manage")
export_perm = require_perm("me_kpi.export")


def _filters(phase: str | None = Query(default=None, pattern="^(MT|TOT|L|E)$"), district_id: int | None = None, team_id: int | None = None, week: int | None = Query(default=None, ge=1, le=60),
             officer_id: int | None = None, date_from: date | None = None, date_to: date | None = None, mine: bool = False) -> dict:
    return {"phase": phase or None, "district_id": district_id, "team_id": team_id, "week": week, "officer_id": officer_id, "date_from": date_from, "date_to": date_to, "mine": mine}


@router.get("/me/kpi/form")
def form_spec(_: User = Depends(view)):
    return me_kpi_form.public_spec()


@router.get("/me/kpi/geo", response_model=GeoBundle)
def geo(db: Session = Depends(get_db), user: User = Depends(view)):
    """The officer's districts with their chiefdoms, sections and SAs: cached on the device for offline use."""
    return svc.geo(db, user)


@router.post("/me/kpi/sync", response_model=SyncOut)
def sync(body: SyncIn, request: Request, db: Session = Depends(get_db), user: User = Depends(collect)):
    """Send one or many reports; a report with a known client_id is updated instead of duplicated."""
    out = svc.sync(db, user, body, can_manage="me_kpi.manage" in getattr(request.state, "permissions", set()))
    if out.created or out.updated:
        audit(db, user, "me_kpi.sync", "me_kpi_report", None, {"created": out.created, "updated": out.updated, "errors": out.errors}, request)
    db.commit()
    return out


@router.get("/me/kpi/reports", response_model=list[ReportOut])
def list_reports(filters: dict = Depends(_filters), limit: int = Query(default=500, ge=1, le=5000), db: Session = Depends(get_db), user: User = Depends(view)):
    rows = svc.query(db, user, **filters)[:limit]
    n = svc.Names(db, rows)
    return [svc.to_out(x, n) for x in rows]


@router.get("/me/kpi/summary", response_model=Summary)
def summary(filters: dict = Depends(_filters), db: Session = Depends(get_db), user: User = Depends(view)):
    return svc.summary(db, user, **filters)


@router.get("/me/kpi/export")
def export(request: Request, format: str = Query(default="xlsx", pattern="^(xlsx|pdf)$"), filters: dict = Depends(_filters), db: Session = Depends(get_db), user: User = Depends(export_perm)):
    report = svc.export(db, user, **filters)
    audit(db, user, "me_kpi.export", "me_kpi_report", None, {"format": format, **{k: str(v) for k, v in filters.items() if v}}, request)
    db.commit()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    if format == "pdf":
        return Response(report_service.to_pdf(report), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="me-kpi-{stamp}.pdf"'})
    return Response(report_service.to_xlsx(report), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="me-kpi-{stamp}.xlsx"'})


@router.get("/me/kpi/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: int, db: Session = Depends(get_db), user: User = Depends(view)):
    x = svc.get(db, user, report_id)
    return svc.to_out(x, svc.Names(db, [x]))


@router.put("/me/kpi/reports/{report_id}", response_model=ReportOut)
def edit_report(report_id: int, body: ReportIn, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    x = svc.edit(db, user, svc.get(db, user, report_id), body)
    audit(db, user, "me_kpi.edit", "me_kpi_report", x.id, {"phase": x.phase, "date": x.report_date.isoformat(), "district_id": x.district_id}, request)
    db.commit()
    return svc.to_out(x, svc.Names(db, [x]))


@router.delete("/me/kpi/reports/{report_id}", status_code=204)
def delete_report(report_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    x = svc.get(db, user, report_id)
    audit(db, user, "me_kpi.delete", "me_kpi_report", x.id, {"phase": x.phase, "date": x.report_date.isoformat()}, request)
    svc.delete(db, x)
    db.commit()
    return Response(status_code=204)
