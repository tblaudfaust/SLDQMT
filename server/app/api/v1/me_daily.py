"""Daily Evaluation: rounds and daily class reports (accounts with the me_daily rights) and the public form page."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import audit, require_perm
from app.core import me_daily_form
from app.db.session import get_db
from app.models import User
from app.schemas.me_daily import PublicRound, PublicSubmitIn, PublicSubmitOut, ReportIn, ReportOut, RoundIn, RoundOut, RoundUpdate, Summary
from app.services import me_daily_service as svc
from app.services import report_service

router = APIRouter(tags=["daily-evaluation"])
view = require_perm("me_daily.view")
manage = require_perm("me_daily.manage")


def _filters(district: str | None = Query(default=None, max_length=60), class_hall: str | None = Query(default=None, max_length=80), trainer: str | None = Query(default=None, max_length=160),
             phase: str | None = Query(default=None, pattern="^(MASTER|TOT|FIELD)$"), date_from: date | None = None, date_to: date | None = None) -> dict:
    return {"district": district or None, "class_hall": class_hall or None, "trainer": trainer or None, "phase": phase or None, "date_from": date_from, "date_to": date_to}


@router.get("/me/daily/form")
def form_spec(_: User = Depends(view)):
    return me_daily_form.public_spec()


@router.get("/me/daily/rounds", response_model=list[RoundOut])
def list_rounds(db: Session = Depends(get_db), _: User = Depends(view)):
    return svc.list_rounds(db)


@router.post("/me/daily/rounds", response_model=RoundOut, status_code=201)
def create_round(body: RoundIn, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    r = svc.create_round(db, user, body)
    audit(db, user, "me_daily_round.create", "me_daily_round", r.id, {"title": r.title, "phase": r.phase}, request)
    db.commit()
    return svc.to_out(db, r)


@router.get("/me/daily/rounds/{round_id}", response_model=RoundOut)
def get_round(round_id: int, db: Session = Depends(get_db), _: User = Depends(view)):
    return svc.to_out(db, svc.get_round(db, round_id))


@router.patch("/me/daily/rounds/{round_id}", response_model=RoundOut)
def update_round(round_id: int, body: RoundUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    r = svc.update_round(db, svc.get_round(db, round_id), body)
    audit(db, user, "me_daily_round.update", "me_daily_round", r.id, body.model_dump(exclude_unset=True, mode="json"), request)
    db.commit()
    return svc.to_out(db, r)


@router.delete("/me/daily/rounds/{round_id}", status_code=204)
def delete_round(round_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    r = svc.get_round(db, round_id)
    audit(db, user, "me_daily_round.delete", "me_daily_round", r.id, {"title": r.title}, request)
    svc.delete_round(db, r)
    db.commit()
    return Response(status_code=204)


@router.get("/me/daily/rounds/{round_id}/summary", response_model=Summary)
def summary(round_id: int, filters: dict = Depends(_filters), db: Session = Depends(get_db), _: User = Depends(view)):
    return svc.summary(db, svc.get_round(db, round_id), **filters)


@router.get("/me/daily/rounds/{round_id}/reports", response_model=list[ReportOut])
def list_reports(round_id: int, filters: dict = Depends(_filters), db: Session = Depends(get_db), _: User = Depends(view)):
    svc.get_round(db, round_id)
    rows = svc.list_reports(db, round_id, **filters)
    editors = svc._editors(db, rows)
    return [svc.report_out(x, editors) for x in rows]


@router.get("/me/daily/rounds/{round_id}/reports/{report_id}", response_model=ReportOut)
def get_report(round_id: int, report_id: int, db: Session = Depends(get_db), _: User = Depends(view)):
    rep = svc.get_report(db, round_id, report_id)
    return svc.report_out(rep, svc._editors(db, [rep]))


@router.put("/me/daily/rounds/{round_id}/reports/{report_id}", response_model=ReportOut)
def edit_report(round_id: int, report_id: int, body: ReportIn, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    rep = svc.edit_report(db, user, svc.get_report(db, round_id, report_id), body)
    audit(db, user, "me_daily_report.edit", "me_daily_report", rep.id, {"round_id": round_id, "class_hall": rep.class_hall, "report_date": rep.report_date.isoformat()}, request)
    db.commit()
    return svc.report_out(rep, svc._editors(db, [rep]))


@router.delete("/me/daily/rounds/{round_id}/reports/{report_id}", status_code=204)
def delete_report(round_id: int, report_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    rep = svc.get_report(db, round_id, report_id)
    audit(db, user, "me_daily_report.delete", "me_daily_report", rep.id, {"round_id": round_id, "class_hall": rep.class_hall, "report_date": rep.report_date.isoformat()}, request)
    svc.delete_report(db, rep)
    db.commit()
    return Response(status_code=204)


@router.get("/me/daily/rounds/{round_id}/export")
def export(round_id: int, request: Request, format: str = Query(default="xlsx", pattern="^(xlsx|pdf)$"), filters: dict = Depends(_filters), db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.get_round(db, round_id)
    report = svc.export(db, r, **filters)
    audit(db, user, "me_daily_round.export", "me_daily_round", r.id, {"format": format, **{k: str(v) for k, v in filters.items() if v}}, request)
    db.commit()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    safe = "".join(c if c.isalnum() else "-" for c in r.title)[:40].strip("-") or "daily-evaluation"
    if format == "pdf":
        return Response(report_service.to_pdf(report), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="daily-{safe}-{stamp}.pdf"'})
    return Response(report_service.to_xlsx(report), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="daily-{safe}-{stamp}.xlsx"'})


# ---- public form page (lead trainers, no sign-in) ----------------------------------------------


@router.get("/public/daily/{token}", response_model=PublicRound)
def public_round(token: str, db: Session = Depends(get_db)):
    r = svc.by_token(db, token)
    return PublicRound(title=r.title, phase=r.phase, period_start=r.period_start, period_end=r.period_end, description=r.description, status=r.status, form=me_daily_form.public_spec())


@router.post("/public/daily/{token}/submit", response_model=PublicSubmitOut)
def public_submit(token: str, body: PublicSubmitIn, db: Session = Depends(get_db)):
    r = svc.by_token(db, token)
    out = svc.public_submit(db, r, body)
    db.commit()
    return out
