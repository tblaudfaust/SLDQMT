"""Facilitator assessment: trainings, their chapters per day and the daily trainer ratings (accounts with the me_fac rights), and the public rating page."""

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import audit, require_perm
from app.core import me_fac_form
from app.db.session import get_db
from app.models import User
from app.schemas.me_daily import AgendaTemplate
from app.schemas.me_fac import AgendaItemIn, AgendaItemOut, AssessmentIn, AssessmentOut, PublicRound, PublicSubmitIn, PublicSubmitOut, RoundIn, RoundOut, RoundUpdate, Summary
from app.services import me_fac_service as svc
from app.services import report_service

router = APIRouter(tags=["facilitator-assessment"])
view = require_perm("me_fac.view")
manage = require_perm("me_fac.manage")


def _filters(district: str | None = Query(default=None, max_length=60), hall: str | None = Query(default=None, max_length=80), trainer: str | None = Query(default=None, max_length=160),
             monitor: str | None = Query(default=None, max_length=160), training_day: int | None = Query(default=None, ge=1, le=60), date_from: date | None = None, date_to: date | None = None) -> dict:
    return {"district": district or None, "hall": hall or None, "trainer": trainer or None, "monitor": monitor or None, "training_day": training_day, "date_from": date_from, "date_to": date_to}


@router.get("/me/facilitators/form")
def form_spec(_: User = Depends(view)):
    return me_fac_form.public_spec()


@router.get("/me/facilitators/agenda-templates", response_model=list[AgendaTemplate])
def agenda_templates(_: User = Depends(view)):
    return svc.agenda_templates()


@router.post("/me/facilitators/agenda/parse")
async def parse_agenda(file: UploadFile = File(...), _: User = Depends(manage)):
    data = await file.read()
    if len(data) > 5_000_000:
        raise HTTPException(413, "The file is larger than 5 MB")
    return svc.parse_agenda_file(file.filename or "agenda.xlsx", data)


@router.get("/me/facilitators/rounds", response_model=list[RoundOut])
def list_rounds(db: Session = Depends(get_db), _: User = Depends(view)):
    return svc.list_rounds(db)


@router.post("/me/facilitators/rounds", response_model=RoundOut, status_code=201)
def create_round(body: RoundIn, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    r = svc.create_round(db, user, body)
    audit(db, user, "me_fac_round.create", "me_fac_round", r.id, {"title": r.title, "phase": r.phase}, request)
    db.commit()
    return svc.to_out(db, r)


@router.get("/me/facilitators/rounds/{round_id}", response_model=RoundOut)
def get_round(round_id: int, db: Session = Depends(get_db), _: User = Depends(view)):
    return svc.to_out(db, svc.get_round(db, round_id))


@router.patch("/me/facilitators/rounds/{round_id}", response_model=RoundOut)
def update_round(round_id: int, body: RoundUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    r = svc.update_round(db, svc.get_round(db, round_id), body)
    audit(db, user, "me_fac_round.update", "me_fac_round", r.id, body.model_dump(exclude_unset=True, mode="json"), request)
    db.commit()
    return svc.to_out(db, r)


@router.delete("/me/facilitators/rounds/{round_id}", status_code=204)
def delete_round(round_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    r = svc.get_round(db, round_id)
    audit(db, user, "me_fac_round.delete", "me_fac_round", r.id, {"title": r.title}, request)
    svc.delete_round(db, r)
    db.commit()
    return Response(status_code=204)


@router.get("/me/facilitators/rounds/{round_id}/agenda", response_model=list[AgendaItemOut])
def get_agenda(round_id: int, db: Session = Depends(get_db), _: User = Depends(view)):
    return svc.agenda_out(svc.get_round(db, round_id))


@router.put("/me/facilitators/rounds/{round_id}/agenda", response_model=list[AgendaItemOut])
def set_agenda(round_id: int, body: list[AgendaItemIn], request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    """Replace the chapters per day that section B of the form lists."""
    r = svc.set_agenda(db, svc.get_round(db, round_id), body)
    audit(db, user, "me_fac_round.agenda", "me_fac_round", r.id, {"items": len(body), "days": len({a.day for a in body})}, request)
    db.commit()
    return svc.agenda_out(r)


@router.get("/me/facilitators/rounds/{round_id}/summary", response_model=Summary)
def summary(round_id: int, filters: dict = Depends(_filters), db: Session = Depends(get_db), _: User = Depends(view)):
    return svc.summary(db, svc.get_round(db, round_id), **filters)


@router.get("/me/facilitators/rounds/{round_id}/assessments", response_model=list[AssessmentOut])
def list_assessments(round_id: int, filters: dict = Depends(_filters), db: Session = Depends(get_db), _: User = Depends(view)):
    svc.get_round(db, round_id)
    rows = svc.list_assessments(db, round_id, **filters)
    ed = svc.editors(db, rows)
    return [svc.to_assessment_out(x, ed) for x in rows]


@router.get("/me/facilitators/rounds/{round_id}/assessments/{assessment_id}", response_model=AssessmentOut)
def get_assessment(round_id: int, assessment_id: int, db: Session = Depends(get_db), _: User = Depends(view)):
    x = svc.get_assessment(db, round_id, assessment_id)
    return svc.to_assessment_out(x, svc.editors(db, [x]))


@router.put("/me/facilitators/rounds/{round_id}/assessments/{assessment_id}", response_model=AssessmentOut)
def edit_assessment(round_id: int, assessment_id: int, body: AssessmentIn, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    x = svc.edit_assessment(db, user, svc.get_assessment(db, round_id, assessment_id), body)
    audit(db, user, "me_fac_assessment.edit", "me_fac_assessment", x.id, {"round_id": round_id, "trainer": x.trainer_name, "date": x.assessment_date.isoformat()}, request)
    db.commit()
    return svc.to_assessment_out(x, svc.editors(db, [x]))


@router.delete("/me/facilitators/rounds/{round_id}/assessments/{assessment_id}", status_code=204)
def delete_assessment(round_id: int, assessment_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    x = svc.get_assessment(db, round_id, assessment_id)
    audit(db, user, "me_fac_assessment.delete", "me_fac_assessment", x.id, {"round_id": round_id, "trainer": x.trainer_name, "date": x.assessment_date.isoformat()}, request)
    svc.delete_assessment(db, x)
    db.commit()
    return Response(status_code=204)


@router.get("/me/facilitators/rounds/{round_id}/export")
def export(round_id: int, request: Request, format: str = Query(default="xlsx", pattern="^(xlsx|pdf)$"), filters: dict = Depends(_filters), db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.get_round(db, round_id)
    report = svc.export(db, r, **filters)
    audit(db, user, "me_fac_round.export", "me_fac_round", r.id, {"format": format, **{k: str(v) for k, v in filters.items() if v}}, request)
    db.commit()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    safe = "".join(c if c.isalnum() else "-" for c in r.title)[:40].strip("-") or "facilitators"
    if format == "pdf":
        return Response(report_service.to_pdf(report), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="facilitators-{safe}-{stamp}.pdf"'})
    return Response(report_service.to_xlsx(report), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="facilitators-{safe}-{stamp}.xlsx"'})


# ---- public rating page (M&E monitors in the halls, no sign-in) ----------------------------------


@router.get("/public/assess/{token}", response_model=PublicRound)
def public_round(token: str, db: Session = Depends(get_db)):
    r = svc.by_token(db, token)
    return PublicRound(title=r.title, phase=r.phase, period_start=r.period_start, period_end=r.period_end, description=r.description, status=r.status, agenda=svc.agenda_out(r), form=me_fac_form.public_spec())


@router.post("/public/assess/{token}/submit", response_model=PublicSubmitOut)
def public_submit(token: str, body: PublicSubmitIn, db: Session = Depends(get_db)):
    r = svc.by_token(db, token)
    out = svc.public_submit(db, r, body)
    db.commit()
    return out
