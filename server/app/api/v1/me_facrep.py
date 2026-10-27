"""Daily Facilitator's Report (ToT, in-person): the public form reached by link or QR code, and the dashboard,
register and exports for the M&E team (me_fac rights, like the facilitator assessment it belongs to)."""

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import audit, require_perm
from app.db.session import get_db
from app.core import me_facrep_form as form
from app.models import User
from app.schemas.me_facrep import PublicRound, PublicSubmitIn, PublicSubmitOut, ReportIn, ReportOut, RoundRow, Summary
from app.services import me_fac_service, report_service
from app.services import me_facrep_service as svc

router = APIRouter(tags=["me-facrep"])
view = require_perm("me_fac.view")
manage = require_perm("me_fac.manage")


def _filters(venue: str | None = Query(default=None, max_length=80), hall: str | None = Query(default=None, max_length=80), training_day: int | None = Query(default=None, ge=1, le=60),
             date_from: date | None = None, date_to: date | None = None) -> dict:
    return {"venue": venue, "hall": hall, "training_day": training_day, "date_from": date_from, "date_to": date_to}


@router.get("/me/facreports/form")
def form_spec(_: User = Depends(view)):
    return form.public_spec()


@router.get("/me/facreports/rounds", response_model=list[RoundRow])
def list_rounds(db: Session = Depends(get_db), _: User = Depends(view)):
    return svc.list_rounds(db)


@router.get("/me/facreports/rounds/{round_id}/summary", response_model=Summary)
def summary(round_id: int, filters: dict = Depends(_filters), db: Session = Depends(get_db), _: User = Depends(view)):
    return svc.summary(db, me_fac_service.get_round(db, round_id), **filters)


@router.get("/me/facreports/rounds/{round_id}/reports", response_model=list[ReportOut])
def list_reports(round_id: int, filters: dict = Depends(_filters), db: Session = Depends(get_db), _: User = Depends(view)):
    me_fac_service.get_round(db, round_id)
    rows = svc.list_reports(db, round_id, **filters)
    ed = svc.editors(db, rows)
    return [svc.to_out(x, ed) for x in rows]


@router.get("/me/facreports/rounds/{round_id}/reports/{report_id}", response_model=ReportOut)
def get_report(round_id: int, report_id: int, db: Session = Depends(get_db), _: User = Depends(view)):
    x = svc.get_report(db, round_id, report_id)
    return svc.to_out(x, svc.editors(db, [x]))


@router.put("/me/facreports/rounds/{round_id}/reports/{report_id}", response_model=ReportOut)
def edit_report(round_id: int, report_id: int, body: ReportIn, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    x = svc.edit_report(db, user, svc.get_report(db, round_id, report_id), body)
    audit(db, user, "me_facrep.edit", "me_fac_report", x.id, {"venue": x.venue, "hall": x.hall, "date": x.report_date.isoformat()}, request)
    db.commit()
    return svc.to_out(x, svc.editors(db, [x]))


@router.delete("/me/facreports/rounds/{round_id}/reports/{report_id}", status_code=204)
def delete_report(round_id: int, report_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    x = svc.get_report(db, round_id, report_id)
    svc.delete_report(db, x)
    audit(db, user, "me_facrep.delete", "me_fac_report", x.id, {"venue": x.venue, "hall": x.hall, "date": x.report_date.isoformat()}, request)
    db.commit()
    return Response(status_code=204)


@router.get("/me/facreports/rounds/{round_id}/export")
def export(round_id: int, request: Request, format: str = Query(default="xlsx", pattern="^(xlsx|pdf)$"), filters: dict = Depends(_filters), db: Session = Depends(get_db), user: User = Depends(view)):
    r = me_fac_service.get_round(db, round_id)
    rep = svc.export(db, r, **filters)
    audit(db, user, "me_facrep.export", "me_fac_round", r.id, {"format": format, **{k: str(v) for k, v in filters.items() if v}}, request)
    db.commit()
    if format == "pdf":
        return Response(report_service.to_pdf(rep), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="facilitator-report-{r.id}.pdf"'})
    return Response(report_service.to_xlsx(rep), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="facilitator-report-{r.id}.xlsx"'})


# ---- public: the lead facilitator's link / QR code --------------------------------------------------------


@router.get("/public/facreport/{token}", response_model=PublicRound)
def public_round(token: str, db: Session = Depends(get_db)):
    return svc.public_round(db, token)


@router.post("/public/facreport/{token}/submit", response_model=PublicSubmitOut)
def public_submit(token: str, body: PublicSubmitIn, db: Session = Depends(get_db)):
    r = me_fac_service.by_token(db, token)
    out = svc.public_submit(db, r, body)
    db.commit()
    return out
