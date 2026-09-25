from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import audit, require_tablet
from app.db.session import get_db
from app.models import Device, DeviceStatus, User
from app.schemas.admin import DeviceOut

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceRegister(BaseModel):
    device_id: str = Field(min_length=8, max_length=36)
    model: str | None = None
    android_version: str | None = None
    app_version: str | None = None


@router.post("/register", response_model=DeviceOut)
def register(body: DeviceRegister, db: Session = Depends(get_db), user: User = Depends(require_tablet)):
    device = db.get(Device, body.device_id)
    now = datetime.now(timezone.utc)
    if device is None:
        device = Device(id=body.device_id, user_id=user.id, model=body.model, android_version=body.android_version, app_version=body.app_version, last_login_at=now)
        db.add(device)
        audit(db, user, "device.register", "device", body.device_id, body.model)
    else:
        if device.user_id != user.id:
            # A tablet handed to another monitor: re-home it and clear its sync state.
            audit(db, user, "device.rehome", "device", body.device_id, f"from user {device.user_id}")
            device.user_id = user.id
            device.last_sync_at = None
            device.pending_reported = 0
        if device.status == DeviceStatus.BLOCKED:
            raise HTTPException(403, "This device has been blocked by an administrator")
        device.model = body.model or device.model
        device.android_version = body.android_version or device.android_version
        device.app_version = body.app_version or device.app_version
        device.last_login_at = now
    db.commit()
    db.refresh(device)
    out = DeviceOut.model_validate(device)
    out.username = user.username
    out.full_name = user.full_name
    return out
