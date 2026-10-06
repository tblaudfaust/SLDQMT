import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, selectinload

from app.api.deps import audit, diff, has_perm, require_perm, snapshot
from app.db.session import get_db
from app.models import Activity, District, EnumerationArea, ErrorCategory, ErrorRecord, ErrorStatus, SupportMethod, Team, User
from app.schemas.common import Page
from app.schemas.dashboard import AgeingBand, Bucket, DeleteIn, ErrorListRow, ErrorUpdate, Filters, MonitorRow, OverdueRow, Summary, TeamRow, TrendPoint
from app.schemas.sync import ErrorWithHistory
from app.services import dashboard_service as ds
from app.services.followup import load_policy, next_follow_up

router = APIRouter(tags=["dashboard"])

view = require_perm("dashboard.view")


def filters(
    district_id: list[int] | None = Query(default=None),
    team_id: int | None = None,
    ea_id: int | None = None,
    category_id: int | None = None,
    status: ErrorStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    received_on: date | None = None,
    resolved_on: date | None = None,
    supervisor_id: int | None = None,
    supervisor: str | None = None,
    enumerator: str | None = None,
    user_id: int | None = None,
    support_method: SupportMethod | None = None,
    overdue_only: bool = False,
    search: str | None = None,
    own_sas: bool | None = None,
) -> Filters:
    return Filters(
        district_id=district_id, team_id=team_id, ea_id=ea_id, category_id=category_id, status=status,
        date_from=date_from, date_to=date_to, received_on=received_on, resolved_on=resolved_on, supervisor_id=supervisor_id, supervisor=supervisor,
        enumerator=enumerator, user_id=user_id, support_method=support_method, overdue_only=overdue_only, search=search, own_sas=own_sas,
    )


@router.get("/dashboard/summary", response_model=Summary)
def summary(f: Filters = Depends(filters), db: Session = Depends(get_db), user: User = Depends(view)):
    return ds.summary(db, user, f)


@router.get("/dashboard/by-district", response_model=list[Bucket])
def by_district(f: Filters = Depends(filters), db: Session = Depends(get_db), user: User = Depends(view)):
    return ds.by_district(db, user, f)


@router.get("/dashboard/by-category", response_model=list[Bucket])
def by_category(f: Filters = Depends(filters), db: Session = Depends(get_db), user: User = Depends(view)):
    return ds.by_category(db, user, f)


@router.get("/dashboard/by-monitor", response_model=list[MonitorRow])
def by_monitor(f: Filters = Depends(filters), db: Session = Depends(get_db), user: User = Depends(view)):
    return ds.by_monitor(db, user, f)


@router.get("/dashboard/by-team", response_model=list[TeamRow])
def by_team(f: Filters = Depends(filters), db: Session = Depends(get_db), user: User = Depends(view)):
    return ds.by_team(db, user, f)


@router.get("/dashboard/trend", response_model=list[TrendPoint])
def trend(granularity: str = Query(default="day", pattern="^(day|week)$"), f: Filters = Depends(filters), db: Session = Depends(get_db), user: User = Depends(view)):
    return ds.trend(db, user, f, granularity)


@router.get("/dashboard/ageing", response_model=list[AgeingBand])
def ageing(f: Filters = Depends(filters), db: Session = Depends(get_db), user: User = Depends(view)):
    return ds.ageing(db, user, f)


@router.get("/dashboard/overdue", response_model=list[OverdueRow])
def overdue(f: Filters = Depends(filters), db: Session = Depends(get_db), user: User = Depends(view)):
    return ds.overdue_list(db, user, f)


@router.get("/errors", response_model=Page[ErrorListRow])
def errors(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    deleted: bool = False,
    f: Filters = Depends(filters),
    db: Session = Depends(get_db),
    user: User = Depends(view),
):
    if deleted and not has_perm(request, "errors.delete"):
        raise HTTPException(403, "You do not have the right: errors.delete")
    items, total = ds.error_list(db, user, f, page, page_size, deleted_only=deleted)
    return Page(items=items, total=total, page=page, page_size=page_size)


def _load(db: Session, user: User, error_id: str, include_deleted: bool = True) -> ErrorRecord:
    q = ds.base_query(db, user, Filters(), include_deleted=include_deleted).where(ErrorRecord.id == error_id).options(
        selectinload(ErrorRecord.follow_ups), selectinload(ErrorRecord.activity)
    )
    record = db.execute(q).scalars().first()
    if record is None:
        raise HTTPException(404, "Error not found in your scope")
    return record


@router.get("/errors/{error_id}", response_model=ErrorWithHistory)
def error_detail(error_id: str, db: Session = Depends(get_db), user: User = Depends(view)):
    return _load(db, user, error_id)


@router.patch("/errors/{error_id}", response_model=ErrorWithHistory)
def error_update(error_id: str, body: ErrorUpdate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_perm("dashboard.view", "errors.edit"))):
    record = _load(db, user, error_id)
    if record.deleted_at is not None:
        raise HTTPException(409, "This error is deleted; restore it first")
    before = snapshot(record)
    changes = body.model_dump(exclude_none=True, exclude={"note"})
    if "team_id" in changes and changes["team_id"] is not None:
        t = db.get(Team, changes["team_id"])
        if t is None or t.district_id != record.district_id:
            raise HTTPException(400, "Team does not belong to the error's district")
    if "ea_id" in changes and changes["ea_id"] is not None and db.get(EnumerationArea, changes["ea_id"]) is None:
        raise HTTPException(400, "Unknown EA")
    if "category_id" in changes and db.get(ErrorCategory, changes["category_id"]) is None:
        raise HTTPException(400, "Unknown category")
    for k, v in changes.items():
        setattr(record, k, v)
    now = datetime.now(timezone.utc)
    status_changed = "status" in changes and changes["status"] != before["status"]
    if status_changed:
        record.last_action_at = now
        if record.status == ErrorStatus.RESOLVED:
            record.resolved_at = now
            record.next_follow_up_at = None
        else:
            record.resolved_at = None
            record.next_follow_up_at = next_follow_up(now, load_policy(db))
    record.client_updated_at = now  # newer than the tablet's copy, so the tablet accepts it at the next pull
    record.server_updated_at = now
    record.version += 1
    db.add(
        Activity(
            id=str(uuid.uuid4()), error_id=record.id, user_id=user.id, device_id=None,
            previous_status=before["status"], new_status=record.status,
            action_taken=body.action_taken if status_changed else "Edited on the dashboard",
            comments=body.note or None, client_at=now,
        )
    )
    changed = diff(before, snapshot(record), ignore=("updated_at", "server_updated_at", "version", "client_updated_at"))
    audit(db, user, "error.update", "error", record.display_id, {"id": record.id, "changes": changed, "note": body.note}, request)
    db.commit()
    return _load(db, user, error_id)


@router.delete("/errors/{error_id}", response_model=ErrorWithHistory)
def error_delete(error_id: str, body: DeleteIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_perm("dashboard.view", "errors.delete"))):
    record = _load(db, user, error_id)
    if record.deleted_at is not None:
        raise HTTPException(409, "Already deleted")
    if not body.reason.strip():
        raise HTTPException(400, "A reason is required")
    now = datetime.now(timezone.utc)
    record.deleted_at = now
    record.deleted_by = user.id
    record.delete_reason = body.reason.strip()
    record.server_updated_at = now
    audit(db, user, "error.delete", "error", record.display_id, {"id": record.id, "reason": body.reason.strip(), "district_id": record.district_id}, request)
    db.commit()
    return _load(db, user, error_id)


@router.post("/errors/{error_id}/restore", response_model=ErrorWithHistory)
def error_restore(error_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(require_perm("dashboard.view", "errors.delete"))):
    record = _load(db, user, error_id)
    if record.deleted_at is None:
        raise HTTPException(409, "Not deleted")
    record.deleted_at = None
    record.deleted_by = None
    record.delete_reason = None
    record.server_updated_at = datetime.now(timezone.utc)
    audit(db, user, "error.restore", "error", record.display_id, {"id": record.id}, request)
    db.commit()
    return _load(db, user, error_id)


@router.get("/districts-in-scope", response_model=list[dict])
def districts_in_scope(db: Session = Depends(get_db), user: User = Depends(view)):
    from app.services.scope import district_ids_for

    scope = district_ids_for(db, user)
    q = db.query(District)
    if scope is not None:
        q = q.filter(District.id.in_(scope))
    return [{"id": d.id, "name": d.name, "region_id": d.region_id} for d in q.order_by(District.name)]
