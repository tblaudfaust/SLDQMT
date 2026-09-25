"""Push/pull synchronisation for tablets.

Push is idempotent: every record carries a tablet-generated UUID. An error
already on the server with the same or a newer client_updated_at is a
duplicate; follow-ups and activity entries are append-only, so a second copy
is simply ignored. Nothing is ever deleted through sync."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import (
    Activity,
    Device,
    DeviceStatus,
    District,
    ErrorCategory,
    ErrorRecord,
    ErrorStatus,
    FollowUp,
    SyncLog,
    User,
)
from app.schemas.sync import (
    ActivityIn,
    ErrorIn,
    ErrorWithHistory,
    FollowUpIn,
    PullResponse,
    PushRequest,
    PushResponse,
    Receipt,
)
from app.services import reference as reference_service
from app.services.followup import load_policy, next_follow_up
from app.services.scope import district_ids_for


class SyncError(Exception):
    def __init__(self, status_code: int, code: str, detail: str):
        self.status_code = status_code
        self.code = code
        self.detail = detail


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def get_active_device(db: Session, user: User, device_id: str) -> Device:
    device = db.get(Device, device_id)
    if device is None or device.user_id != user.id:
        raise SyncError(403, "DEVICE_UNKNOWN", "This device is not registered to the signed-in user")
    if device.status != DeviceStatus.ACTIVE:
        raise SyncError(403, "DEVICE_BLOCKED", "This device has been blocked by an administrator")
    return device


def _apply_error(db: Session, user: User, device: Device, item: ErrorIn, scope: list[int] | None, policy) -> Receipt:
    if scope is not None and item.district_id not in scope:
        return Receipt(kind="error", id=item.id, result="rejected", reason="NOT_IN_SCOPE")
    if db.get(District, item.district_id) is None:
        return Receipt(kind="error", id=item.id, result="rejected", reason="UNKNOWN_DISTRICT")
    if db.get(ErrorCategory, item.category_id) is None:
        return Receipt(kind="error", id=item.id, result="rejected", reason="UNKNOWN_CATEGORY")

    existing = db.get(ErrorRecord, item.id)
    if existing is not None and existing.user_id != user.id:
        return Receipt(kind="error", id=item.id, result="rejected", reason="NOT_OWNER")
    if existing is not None and existing.deleted_at is not None:
        # Deleted from the dashboard; the tablet learns this at the next pull.
        return Receipt(kind="error", id=item.id, result="rejected", reason="DELETED")

    incoming_updated = _aware(item.client_updated_at)
    if existing is not None and _aware(existing.client_updated_at) >= incoming_updated:
        return Receipt(
            kind="error",
            id=item.id,
            result="duplicate",
            version=existing.version,
            next_follow_up_at=existing.next_follow_up_at,
        )

    payload = item.model_dump(exclude={"id"})
    if existing is None:
        record = ErrorRecord(id=item.id, user_id=user.id, device_id=device.id, version=1, **payload)
        db.add(record)
    else:
        for key, value in payload.items():
            setattr(existing, key, value)
        existing.device_id = device.id
        existing.version = existing.version + 1
        record = existing

    if record.status == ErrorStatus.RESOLVED:
        record.next_follow_up_at = None
        record.resolved_at = record.resolved_at or incoming_updated
    else:
        record.resolved_at = None
        record.next_follow_up_at = next_follow_up(_aware(record.last_action_at), policy)
    record.server_updated_at = _now()
    db.flush()
    return Receipt(
        kind="error", id=item.id, result="applied", version=record.version, next_follow_up_at=record.next_follow_up_at
    )


def _apply_follow_up(db: Session, user: User, device: Device, item: FollowUpIn) -> Receipt:
    if db.get(FollowUp, item.id) is not None:
        return Receipt(kind="follow_up", id=item.id, result="duplicate")
    error = db.get(ErrorRecord, item.error_id)
    if error is None:
        return Receipt(kind="follow_up", id=item.id, result="rejected", reason="UNKNOWN_ERROR")
    if error.user_id != user.id:
        return Receipt(kind="follow_up", id=item.id, result="rejected", reason="NOT_OWNER")
    db.add(FollowUp(user_id=user.id, device_id=device.id, **item.model_dump()))
    error.server_updated_at = _now()
    db.flush()
    return Receipt(kind="follow_up", id=item.id, result="applied")


def _apply_activity(db: Session, user: User, device: Device, item: ActivityIn) -> Receipt:
    if db.get(Activity, item.id) is not None:
        return Receipt(kind="activity", id=item.id, result="duplicate")
    error = db.get(ErrorRecord, item.error_id)
    if error is None:
        return Receipt(kind="activity", id=item.id, result="rejected", reason="UNKNOWN_ERROR")
    if error.user_id != user.id:
        return Receipt(kind="activity", id=item.id, result="rejected", reason="NOT_OWNER")
    db.add(Activity(user_id=user.id, device_id=device.id, **item.model_dump()))
    db.flush()
    return Receipt(kind="activity", id=item.id, result="applied")


def push(db: Session, user: User, req: PushRequest) -> PushResponse:
    total = len(req.errors) + len(req.follow_ups) + len(req.activity)
    if total > settings.SYNC_BATCH_MAX:
        raise SyncError(413, "BATCH_TOO_LARGE", f"At most {settings.SYNC_BATCH_MAX} records per push")
    device = get_active_device(db, user, req.device_id)
    scope = district_ids_for(db, user)
    policy = load_policy(db)
    log = SyncLog(device_id=device.id, user_id=user.id)
    db.add(log)

    receipts: list[Receipt] = []
    # Errors first (in client order), then follow-ups and activity that reference them.
    for item in sorted(req.errors, key=lambda e: e.client_updated_at):
        receipts.append(_apply_error(db, user, device, item, scope, policy))
    for item in sorted(req.follow_ups, key=lambda f: f.at):
        receipts.append(_apply_follow_up(db, user, device, item))
    for item in sorted(req.activity, key=lambda a: a.client_at):
        receipts.append(_apply_activity(db, user, device, item))

    applied = sum(1 for r in receipts if r.result == "applied")
    duplicates = sum(1 for r in receipts if r.result == "duplicate")
    rejected = sum(1 for r in receipts if r.result == "rejected")

    device.last_sync_at = _now()
    device.pending_reported = max(req.pending_count - applied - duplicates, 0)
    if req.app_version:
        device.app_version = req.app_version
    log.pushed = applied
    log.rejected = rejected
    log.finished_at = _now()
    log.result = "OK" if rejected == 0 else "PARTIAL"
    db.commit()
    return PushResponse(
        receipts=receipts, applied=applied, duplicates=duplicates, rejected=rejected, server_time=_now()
    )


def _parse_cursor(cursor: str | None) -> datetime | None:
    if not cursor:
        return None
    try:
        return _aware(datetime.fromisoformat(cursor))
    except ValueError:
        raise SyncError(400, "BAD_CURSOR", "cursor must be an ISO-8601 timestamp")


def pull(
    db: Session, user: User, device_id: str, cursor: str | None, reference_version: str | None, limit: int = 500
) -> PullResponse:
    device = get_active_device(db, user, device_id)
    since = _parse_cursor(cursor)

    q = (
        select(ErrorRecord)
        .options(selectinload(ErrorRecord.follow_ups), selectinload(ErrorRecord.activity))
        .where(ErrorRecord.user_id == user.id)
        .order_by(ErrorRecord.server_updated_at, ErrorRecord.id)
    )
    if since is not None:
        q = q.where(ErrorRecord.server_updated_at > since)
    rows = db.execute(q.limit(limit + 1)).scalars().all()
    more = len(rows) > limit
    rows = rows[:limit]

    if rows:
        next_cursor = max(_aware(r.server_updated_at) for r in rows).isoformat()
    else:
        next_cursor = cursor or _now().isoformat()

    scope = district_ids_for(db, user)
    current_version = reference_service.reference_version(db, scope)
    bundle = None
    if reference_version != current_version:
        bundle = reference_service.build_bundle(db, user)

    device.last_sync_at = _now()
    db.commit()
    return PullResponse(
        cursor=next_cursor,
        errors=[ErrorWithHistory.model_validate(r) for r in rows],
        reference=bundle,
        reference_version=current_version,
        settings=reference_service.current_settings(db),
        server_time=_now(),
        more=more,
    )
