"""Monitoring & Evaluation: training evaluations (M&E staff) and the public evaluation page."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import audit, require_perm
from app.core import me_form
from app.db.session import get_db
from app.models import User
from app.schemas.me import (
    EvaluationIn,
    EvaluationOut,
    EvaluationUpdate,
    PublicEvaluation,
    RegisterIn,
    RegisterOut,
    RespondentOut,
    Results,
    SubmitIn,
    SubmitOut,
)
from app.services import me_service, report_service

router = APIRouter(tags=["monitoring-evaluation"])
view = require_perm("me.view")
manage = require_perm("me.manage")


# ---- M&E staff ----------------------------------------------------------------


@router.get("/me/form")
def form_spec(_: User = Depends(view)):
    """The questionnaire as rendered on the public page, for previews."""
    return me_form.public_spec()


@router.get("/me/evaluations", response_model=list[EvaluationOut])
def list_evaluations(db: Session = Depends(get_db), _: User = Depends(view)):
    return me_service.list_evaluations(db)


@router.post("/me/evaluations", response_model=EvaluationOut, status_code=201)
def create_evaluation(body: EvaluationIn, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    e = me_service.create_evaluation(db, user, body)
    audit(db, user, "me_evaluation.create", "me_evaluation", e.id, {"title": e.title, "mode": e.training_mode}, request)
    db.commit()
    return me_service.to_out(db, e)


@router.get("/me/evaluations/{evaluation_id}", response_model=EvaluationOut)
def get_evaluation(evaluation_id: int, db: Session = Depends(get_db), _: User = Depends(view)):
    return me_service.to_out(db, me_service.get_evaluation(db, evaluation_id))


@router.patch("/me/evaluations/{evaluation_id}", response_model=EvaluationOut)
def update_evaluation(evaluation_id: int, body: EvaluationUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    e = me_service.update_evaluation(db, me_service.get_evaluation(db, evaluation_id), body)
    audit(db, user, "me_evaluation.update", "me_evaluation", e.id, body.model_dump(exclude_unset=True, mode="json"), request)
    db.commit()
    return me_service.to_out(db, e)


@router.delete("/me/evaluations/{evaluation_id}", status_code=204)
def delete_evaluation(evaluation_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    e = me_service.get_evaluation(db, evaluation_id)
    audit(db, user, "me_evaluation.delete", "me_evaluation", e.id, {"title": e.title, "registered": len(e.respondents)}, request)
    me_service.delete_evaluation(db, e)
    db.commit()
    return Response(status_code=204)


@router.get("/me/evaluations/{evaluation_id}/respondents", response_model=list[RespondentOut])
def respondents(evaluation_id: int, db: Session = Depends(get_db), _: User = Depends(view)):
    me_service.get_evaluation(db, evaluation_id)
    return me_service.respondents(db, evaluation_id)


@router.delete("/me/evaluations/{evaluation_id}/responses/{response_id}", status_code=204)
def delete_response(evaluation_id: int, response_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(manage)):
    me_service.get_evaluation(db, evaluation_id)
    r = me_service.delete_response(db, evaluation_id, response_id)
    audit(db, user, "me_response.delete", "me_response", r.id, {"evaluation_id": evaluation_id, "respondent_id": r.respondent_id}, request)
    db.commit()
    return Response(status_code=204)


@router.get("/me/evaluations/{evaluation_id}/results", response_model=Results)
def results(evaluation_id: int, district: str | None = Query(default=None, max_length=60), db: Session = Depends(get_db), _: User = Depends(view)):
    """Results, optionally limited to one district (A04); the by-district table is always national."""
    return me_service.results(db, me_service.get_evaluation(db, evaluation_id), district or None)


@router.get("/me/evaluations/{evaluation_id}/export")
def export(evaluation_id: int, request: Request, format: str = Query(default="xlsx", pattern="^(xlsx|pdf)$"), db: Session = Depends(get_db), user: User = Depends(view)):
    e = me_service.get_evaluation(db, evaluation_id)
    report = me_service.export(db, e)
    audit(db, user, "me_evaluation.export", "me_evaluation", e.id, {"format": format}, request)
    db.commit()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    safe = "".join(c if c.isalnum() else "-" for c in e.title)[:40].strip("-") or "evaluation"
    if format == "pdf":
        return Response(report_service.to_pdf(report), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe}-{stamp}.pdf"'})
    return Response(
        report_service.to_xlsx(report),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe}-{stamp}.xlsx"'},
    )


# ---- public evaluation page (no sign-in) --------------------------------------


@router.get("/public/evaluations/{token}", response_model=PublicEvaluation)
def public_evaluation(token: str, db: Session = Depends(get_db)):
    e = me_service.by_token(db, token)
    return PublicEvaluation(
        title=e.title, training_mode=e.training_mode, period_start=e.period_start, period_end=e.period_end,
        description=e.description, status=e.status, form=me_form.public_spec(),
    )


@router.post("/public/evaluations/{token}/register", response_model=RegisterOut)
def public_register(token: str, body: RegisterIn, db: Session = Depends(get_db)):
    e = me_service.by_token(db, token)
    out = me_service.register(db, e, body)
    db.commit()
    return out


@router.post("/public/evaluations/{token}/submit", response_model=SubmitOut)
def public_submit(token: str, body: SubmitIn, request: Request, db: Session = Depends(get_db)):
    e = me_service.by_token(db, token)
    out = me_service.submit(db, e, body, request.headers.get("user-agent"))
    db.commit()
    return out
