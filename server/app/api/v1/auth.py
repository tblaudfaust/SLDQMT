from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import audit, get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.db.session import get_db
from app.models import Device, RefreshToken, User
from app.schemas.admin import ChangePasswordIn
from app.schemas.auth import LoginRequest, RefreshRequest, ScopeOut, TokenPair, UserOut
from app.services.permission_service import effective_permissions
from app.services.reference import current_settings
from app.services.scope import district_ids_for

router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(db: Session, user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.district_ids = district_ids_for(db, user)
    out.scopes = [ScopeOut(region_id=s.region_id, district_id=s.district_id) for s in user.scopes]
    out.permissions = sorted(effective_permissions(db, user))
    return out


def issue_tokens(db: Session, user: User, device_id: str | None) -> TokenPair:
    raw = generate_refresh_token()
    db.add(RefreshToken(user_id=user.id, device_id=device_id, token_hash=hash_refresh_token(raw), expires_at=refresh_token_expiry()))
    access = create_access_token(str(user.id), {"role": user.role.value, "username": user.username})
    db.commit()
    return TokenPair(
        access_token=access,
        refresh_token=raw,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_out(db, user),
        settings=current_settings(db),
    )


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    user = db.execute(select(User).where(User.username == body.username.strip().lower())).scalars().first()
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    if user.locked_until and user.locked_until.replace(tzinfo=user.locked_until.tzinfo or timezone.utc) > now:
        raise HTTPException(status.HTTP_423_LOCKED, "Account temporarily locked after failed logins")
    if not verify_password(body.password, user.password_hash):
        user.failed_logins += 1
        if user.failed_logins >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
            user.failed_logins = 0
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now
    if body.device_id:
        device = db.get(Device, body.device_id)
        if device and device.user_id == user.id:
            device.last_login_at = now
    audit(db, user, "auth.login", "user", user.id, body.device_id)
    return issue_tokens(db, user, body.device_id)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    token = db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(body.refresh_token))).scalars().first()
    now = datetime.now(timezone.utc)
    if token is None or token.revoked or token.expires_at.replace(tzinfo=token.expires_at.tzinfo or timezone.utc) < now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token invalid")
    user = db.get(User, token.user_id)
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive")
    token.revoked = True
    return issue_tokens(db, user, token.device_id)


@router.post("/logout", status_code=204)
def logout(body: RefreshRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    token = db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(body.refresh_token))).scalars().first()
    if token and token.user_id == user.id:
        token.revoked = True
        db.commit()


@router.get("/me", response_model=UserOut)
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return user_out(db, user)


@router.post("/change-password", status_code=204)
def change_password(body: ChangePasswordIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    if body.current_password == body.new_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose a different password")
    user.password_hash = hash_password(body.new_password)
    audit(db, user, "auth.change_password", "user", user.id, None, request)
    db.commit()
