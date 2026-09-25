from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import audit, diff, has_perm, require_perm, snapshot
from app.db.session import get_db
from app.models import ReportStatus, User
from app.schemas.dqm_report import (
    ERROR_BANDS,
    ISSUE_TYPES,
    QUALITY_AREAS,
    DeleteIn,
    DqmReportIn,
    DqmReportListRow,
    DqmReportOut,
    DqmSummary,
    ReceiveIn,
)
from app.services import dqm_analytics_service as analytics_service
from app.services import dqm_report_service as svc
from app.services import report_service

router = APIRouter(prefix="/dqm-reports", tags=["dqm-reports"])

view = require_perm("daily_reports.view")
view_analytics = require_perm("analytics.view")


def _perms(request: Request) -> set[str]:
    return getattr(request.state, "permissions", set())


def _file(report: report_service.Report, fmt: str) -> Response:
    stamp = report.generated_at.strftime("%Y%m%d-%H%M")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in report.title)
    if fmt == "pdf":
        return Response(report_service.to_pdf(report), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe}-{stamp}.pdf"'})
    return Response(
        report_service.to_xlsx(report),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe}-{stamp}.xlsx"'},
    )


@router.get("/options")
def options(request: Request, user: User = Depends(view)):
    p = _perms(request)
    return {
        "error_bands": ERROR_BANDS,
        "issue_types": ISSUE_TYPES,
        "quality_areas": QUALITY_AREAS,
        "can_create": "daily_reports.create" in p,
        "can_edit": "daily_reports.edit" in p,
        "can_submit": "daily_reports.submit" in p,
        "can_receive": "daily_reports.receive" in p,
        "can_delete": "daily_reports.delete" in p,
    }


@router.get("", response_model=list[DqmReportListRow])
def list_reports(
    request: Request,
    district_id: int | None = None,
    region_id: int | None = None,
    status: ReportStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    deleted: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(view),
):
    if deleted and not has_perm(request, "daily_reports.delete"):
        raise HTTPException(403, "You do not have the right: daily_reports.delete")
    return svc.list_reports(db, user, district_id, region_id, status, date_from, date_to, deleted)


@router.get("/summary", response_model=DqmSummary)
def summary(
    level: str = Query(default="region", pattern="^(national|region)$"),
    region_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(view_analytics),
):
    return svc.summary(db, user, level, region_id, date_from, date_to)


@router.get("/analytics", response_model=analytics_service.Analytics)
def analytics(
    level: str = Query(default="district", pattern="^(district|region|national)$"),
    district_id: int | None = None,
    region_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(view_analytics),
):
    return analytics_service.analytics(db, user, level, district_id, region_id, date_from, date_to)


@router.get("/summary/export")
def summary_export(
    request: Request,
    level: str = Query(default="region", pattern="^(national|region)$"),
    region_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    format: str = Query(default="xlsx", pattern="^(xlsx|pdf)$"),
    db: Session = Depends(get_db),
    user: User = Depends(view_analytics),
):
    s = svc.summary(db, user, level, region_id, date_from, date_to)
    audit(db, user, "dqm_summary.export", "dqm_summary", level, f"region={region_id} from={date_from} to={date_to}", request)
    db.commit()
    return _file(svc.export_summary(s), format)


@router.post("", response_model=DqmReportOut, status_code=201)
def create(body: DqmReportIn, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.create(db, user, _perms(request), body)
    audit(db, user, "dqm_report.create", "dqm_report", r.id, {"district_id": r.district_id, "report_date": r.report_date}, request)
    db.commit()
    return svc.to_out(db, r)


@router.get("/{report_id}", response_model=DqmReportOut)
def get(report_id: int, db: Session = Depends(get_db), user: User = Depends(view)):
    return svc.to_out(db, svc.get_in_scope(db, user, report_id))


@router.put("/{report_id}", response_model=DqmReportOut)
def update(report_id: int, body: DqmReportIn, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    before = snapshot(svc.get_in_scope(db, user, report_id))
    r = svc.update(db, user, _perms(request), report_id, body)
    audit(db, user, "dqm_report.update", "dqm_report", r.id, {"changes": diff(before, snapshot(r))}, request)
    db.commit()
    return svc.to_out(db, r)


@router.post("/{report_id}/submit", response_model=DqmReportOut)
def submit(report_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.submit(db, user, _perms(request), report_id)
    audit(db, user, "dqm_report.submit", "dqm_report", r.id, None, request)
    db.commit()
    return svc.to_out(db, r)


@router.post("/{report_id}/receive", response_model=DqmReportOut)
def receive(report_id: int, body: ReceiveIn, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.receive(db, user, _perms(request), report_id, body.comment)
    audit(db, user, "dqm_report.receive", "dqm_report", r.id, body.comment, request)
    db.commit()
    return svc.to_out(db, r)


@router.delete("/{report_id}", response_model=DqmReportOut)
def delete(report_id: int, body: DeleteIn, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.delete(db, user, _perms(request), report_id, body.reason)
    audit(db, user, "dqm_report.delete", "dqm_report", r.id, {"district_id": r.district_id, "report_date": r.report_date, "reason": body.reason}, request)
    db.commit()
    return svc.to_out(db, r)


@router.post("/{report_id}/restore", response_model=DqmReportOut)
def restore(report_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.restore(db, user, _perms(request), report_id)
    audit(db, user, "dqm_report.restore", "dqm_report", r.id, None, request)
    db.commit()
    return svc.to_out(db, r)


@router.get("/{report_id}/export")
def export(report_id: int, format: str = Query(default="pdf", pattern="^(xlsx|pdf)$"), db: Session = Depends(get_db), user: User = Depends(view)):
    return _file(svc.export_report(db, user, report_id), format)
