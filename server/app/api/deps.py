import json
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import AuditLog, User
from app.models.user import Role
from app.services.permission_service import effective_permissions

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_token(creds.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive")
    request.state.permissions = effective_permissions(db, user)
    request.state.ip = request.client.host if request.client else None
    return user


def has_perm(request: Request, code: str) -> bool:
    return code in getattr(request.state, "permissions", set())


def require_perm(*codes: str) -> Callable[..., User]:
    """The user must hold every listed permission."""

    def dep(request: Request, user: User = Depends(get_current_user)) -> User:
        missing = [c for c in codes if not has_perm(request, c)]
        if missing:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"You do not have the right: {', '.join(missing)}")
        return user

    return dep


def require_roles(*roles: Role) -> Callable[..., User]:
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed for your role")
        return user

    return dep


require_admin = require_perm("users.manage")
require_web = require_roles(Role.DISTRICT_DQM, Role.REGIONAL, Role.NATIONAL_DQM, Role.ADMIN)
require_tablet = require_perm("sync.use")


def _jsonable(v: Any):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if hasattr(v, "value"):
        return v.value
    return v


def diff(before: dict | None, after: dict | None, ignore: tuple[str, ...] = ("updated_at", "server_updated_at", "version")) -> dict[str, list]:
    """Field-level changes as {field: [old, new]}, skipping unchanged and bookkeeping fields."""
    before = before or {}
    after = after or {}
    out: dict[str, list] = {}
    for k in sorted(set(before) | set(after)):
        if k in ignore:
            continue
        b, a = _jsonable(before.get(k)), _jsonable(after.get(k))
        if b != a:
            out[k] = [b, a]
    return out


def snapshot(obj) -> dict:
    """Column values of an ORM row, for before/after comparison."""
    return {c.key: getattr(obj, c.key) for c in obj.__table__.columns}


def audit(db: Session, user: User | None, action: str, entity: str | None = None, entity_id=None, detail: str | dict | None = None, request: Request | None = None):
    """Record who did what. `detail` may be text or a JSON-able dict (for example a diff)."""
    if isinstance(detail, dict):
        text = json.dumps(detail, default=_jsonable)
        if len(text) > 4000:
            text = text[:3990] + "…"
        detail = text
    db.add(
        AuditLog(
            at=datetime.now(timezone.utc),
            user_id=user.id if user else None,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            detail=detail,
            ip=getattr(request.state, "ip", None) if request is not None else None,
        )
    )
