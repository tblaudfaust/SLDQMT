from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import audit, diff, has_perm, require_perm, snapshot
from app.db.session import get_db
from app.models import CheckoutStatus, ClearanceDecision, StaffRole, User
from app.schemas.exit_checkout import APPROVALS, CHECKLIST, DECISIONS, ITEMS, CheckoutIn, CheckoutListRow, CheckoutOut, ClearanceIn, DeleteIn, ExitSummary, SignIn
from app.services import exit_checkout_service as svc
from app.services import report_service

router = APIRouter(prefix="/exit-checkouts", tags=["exit-checkouts"])

view = require_perm("exit_checkouts.view")


def _perms(request: Request) -> set[str]:
    return getattr(request.state, "permissions", set())


def _file(report: report_service.Report, fmt: str) -> Response:
    stamp = report.generated_at.strftime("%Y%m%d-%H%M")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in report.title)[:80]
    if fmt == "pdf":
        return Response(report_service.to_pdf(report), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe}-{stamp}.pdf"'})
    return Response(report_service.to_xlsx(report), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{safe}-{stamp}.xlsx"'})


@router.get("/options")
def options(request: Request, user: User = Depends(view)):
    p = _perms(request)
    return {
        "checklist": [{"n": n, "text": t} for n, t in CHECKLIST],
        "items": [{"code": c, "text": t} for c, t in ITEMS],
        "approvals": [{"role": c, "text": t} for c, t in APPROVALS],
        "decisions": DECISIONS,
        "can_create": "exit_checkouts.create" in p,
        "can_edit": "exit_checkouts.edit" in p,
        "can_submit": "exit_checkouts.submit" in p,
        "can_sign": "exit_checkouts.sign" in p,
        "can_clear": "exit_checkouts.clear" in p,
        "can_delete": "exit_checkouts.delete" in p,
        # kept for older clients
        "can_national": "exit_checkouts.sign" in p and "exit_checkouts.clear" in p,
    }


@router.get("", response_model=list[CheckoutListRow])
def list_checkouts(
    request: Request,
    district_id: int | None = None, region_id: int | None = None, role: StaffRole | None = None,
    status: CheckoutStatus | None = None, decision: ClearanceDecision | None = None, search: str | None = None, deleted: bool = False,
    db: Session = Depends(get_db), user: User = Depends(view),
):
    if deleted and not has_perm(request, "exit_checkouts.delete"):
        raise HTTPException(403, "You do not have the right: exit_checkouts.delete")
    return svc.list_checkouts(db, user, district_id, region_id, role, status, decision, search, deleted)


@router.get("/summary", response_model=ExitSummary)
def summary(level: str = Query(default="district", pattern="^(district|region|national)$"), district_id: int | None = None, region_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(view)):
    return svc.summary(db, user, level, district_id, region_id)


@router.get("/summary/export")
def summary_export(request: Request, level: str = Query(default="district", pattern="^(district|region|national)$"), district_id: int | None = None, region_id: int | None = None, format: str = Query(default="xlsx", pattern="^(xlsx|pdf)$"), db: Session = Depends(get_db), user: User = Depends(view)):
    audit(db, user, "exit_summary.export", "exit_summary", level, f"district={district_id} region={region_id}", request)
    db.commit()
    return _file(svc.export_summary(svc.summary(db, user, level, district_id, region_id)), format)


@router.post("", response_model=CheckoutOut, status_code=201)
def create(body: CheckoutIn, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.create(db, user, _perms(request), body)
    audit(db, user, "exit_checkout.create", "exit_checkout", r.id, {"staff_name": r.staff_name, "role": r.role, "district_id": r.district_id}, request)
    db.commit()
    return svc.to_out(db, r)


@router.get("/{checkout_id}", response_model=CheckoutOut)
def get(checkout_id: int, db: Session = Depends(get_db), user: User = Depends(view)):
    return svc.to_out(db, svc.get_in_scope(db, user, checkout_id))


@router.put("/{checkout_id}", response_model=CheckoutOut)
def update(checkout_id: int, body: CheckoutIn, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    before = snapshot(svc.get_in_scope(db, user, checkout_id))
    r = svc.update(db, user, _perms(request), checkout_id, body)
    audit(db, user, "exit_checkout.update", "exit_checkout", r.id, {"changes": diff(before, snapshot(r))}, request)
    db.commit()
    return svc.to_out(db, r)


@router.post("/{checkout_id}/submit", response_model=CheckoutOut)
def submit(checkout_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.submit(db, user, _perms(request), checkout_id)
    audit(db, user, "exit_checkout.submit", "exit_checkout", r.id, None, request)
    db.commit()
    return svc.to_out(db, r)


@router.post("/{checkout_id}/national-sign", response_model=CheckoutOut)
def national_sign(checkout_id: int, body: SignIn, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.national_sign(db, user, _perms(request), checkout_id, body.comment)
    audit(db, user, "exit_checkout.national_sign", "exit_checkout", r.id, body.comment, request)
    db.commit()
    return svc.to_out(db, r)


@router.post("/{checkout_id}/clearance", response_model=CheckoutOut)
def clearance(checkout_id: int, body: ClearanceIn, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.clearance(db, user, _perms(request), checkout_id, body)
    audit(db, user, "exit_checkout.clearance", "exit_checkout", r.id, {"decision": body.decision, "deadline": body.deadline, "issues": body.outstanding_issues}, request)
    db.commit()
    return svc.to_out(db, r)


@router.delete("/{checkout_id}", response_model=CheckoutOut)
def delete(checkout_id: int, body: DeleteIn, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.delete(db, user, _perms(request), checkout_id, body.reason)
    audit(db, user, "exit_checkout.delete", "exit_checkout", r.id, {"staff_name": r.staff_name, "reason": body.reason}, request)
    db.commit()
    return svc.to_out(db, r)


@router.post("/{checkout_id}/restore", response_model=CheckoutOut)
def restore(checkout_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(view)):
    r = svc.restore(db, user, _perms(request), checkout_id)
    audit(db, user, "exit_checkout.restore", "exit_checkout", r.id, None, request)
    db.commit()
    return svc.to_out(db, r)


@router.get("/{checkout_id}/export")
def export(checkout_id: int, format: str = Query(default="pdf", pattern="^(xlsx|pdf)$"), db: Session = Depends(get_db), user: User = Depends(view)):
    return _file(svc.export_checkout(db, user, checkout_id), format)
