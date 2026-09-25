from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_tablet
from app.db.session import get_db
from app.models import User
from app.schemas.reference import ReferenceBundle
from app.schemas.sync import PullResponse, PushRequest, PushResponse
from app.services import reference as reference_service
from app.services import sync_service
from app.services.scope import district_ids_for
from app.services.sync_service import SyncError

router = APIRouter(tags=["sync"])


def _raise(e: SyncError):
    raise HTTPException(e.status_code, {"code": e.code, "detail": e.detail})


@router.post("/sync/push", response_model=PushResponse)
def push(body: PushRequest, db: Session = Depends(get_db), user: User = Depends(require_tablet)):
    try:
        return sync_service.push(db, user, body)
    except SyncError as e:
        db.rollback()
        _raise(e)


@router.get("/sync/pull", response_model=PullResponse)
def pull(
    device_id: str = Query(min_length=1, max_length=36),
    cursor: str | None = None,
    reference_version: str | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(require_tablet),
):
    try:
        return sync_service.pull(db, user, device_id, cursor, reference_version, limit)
    except SyncError as e:
        _raise(e)


@router.get("/reference", response_model=ReferenceBundle | None)
def reference(version: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    current = reference_service.reference_version(db, district_ids_for(db, user))
    if version == current:
        return None
    return reference_service.build_bundle(db, user)
