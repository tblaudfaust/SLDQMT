"""M&E Field Tool (KPIs): the form spec and geography the field app caches, offline-safe sync of reports,
the register, the dashboard summary and exports. Scoped by the officer's districts."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import audit, require_perm
from app.core import me_kpi_form
from app.db.session import get_db
from app.models import User
from app.schemas.me_kpi import FieldAccountIn, FieldAccountOptions, FieldAccountOut, FieldAccountUpdate, GeoBundle, GeoEa, ReportIn, ReportOut, Summary, SyncIn, SyncOut
from app.services import me_kpi_service as svc
from app.services import report_service

router = APIRouter(tags=["me-kpi"])
view = require_perm("me_kpi.view")
collect = require_perm("me_kpi.collect")
manage = require_perm("me_kpi.manage")
export_perm = require_perm("me_kpi.export")
accounts_perm = require_perm("me_kpi.accounts")


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


@router.get("/me/kpi/eas", response_model=list[GeoEa])
def eas(team_id: int, db: Session = Depends(get_db), user: User = Depends(view)):
    """The EAs of one SA (for the national scope, whose bundle does not carry the EA list)."""
    return svc.eas_for_team(db, user, team_id)


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


# ---- field accounts: the M&E lead creates the officers who use the app ---------------------------


@router.get("/me/kpi/accounts/options", response_model=FieldAccountOptions)
def account_options(db: Session = Depends(get_db), _: User = Depends(accounts_perm)):
    return svc.account_options(db)


@router.get("/me/kpi/accounts", response_model=list[FieldAccountOut])
def list_accounts(db: Session = Depends(get_db), _: User = Depends(accounts_perm)):
    return svc.list_accounts(db)


@router.post("/me/kpi/accounts", response_model=FieldAccountOut, status_code=201)
def create_account(body: FieldAccountIn, request: Request, db: Session = Depends(get_db), user: User = Depends(accounts_perm)):
    out = svc.create_account(db, body)
    audit(db, user, "me_kpi.account_create", "user", out.id, {"username": out.username, "role": out.role, "district_ids": out.district_ids, "region_ids": out.region_ids}, request)
    db.commit()
    return out


@router.patch("/me/kpi/accounts/{user_id}", response_model=FieldAccountOut)
def update_account(user_id: int, body: FieldAccountUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(accounts_perm)):
    out = svc.update_account(db, user_id, body)
    audit(db, user, "me_kpi.account_update", "user", out.id, body.model_dump(exclude_unset=True), request)
    db.commit()
    return out


@router.post("/me/kpi/accounts/{user_id}/reset-password", response_model=FieldAccountOut)
def reset_account_password(user_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(accounts_perm)):
    out = svc.reset_account_password(db, user_id)
    audit(db, user, "me_kpi.account_reset", "user", out.id, {"username": out.username}, request)
    db.commit()
    return out


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
