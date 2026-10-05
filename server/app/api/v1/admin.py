import secrets
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import audit, diff, require_perm, require_web, snapshot
from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSIONS
from app.core.security import hash_password
from app.db.session import get_db
from app.models import (
    AuditLog,
    Device,
    District,
    DqmDailyReport,
    Enumerator,
    EnumerationArea,
    ErrorCategory,
    ErrorRecord,
    ErrorSource,
    ExitCheckout,
    RefreshToken,
    Region,
    Setting,
    Supervisor,
    Team,
    User,
    UserScope,
)
from app.models.user import Role
from app.schemas.admin import (
    AuditOut,
    DeviceOut,
    DeviceStatusUpdate,
    ImportResult,
    PasswordResetIn,
    PasswordResetOut, PinResetOut,
    PermissionInfo,
    RoleMatrix,
    RolePermissionsIn,
    SettingsUpdate,
    UserActivity,
    UserAdminOut,
    UserCreate,
    UserImportResult,
    UserPermissionsIn,
    UserPermissionsOut,
    UserStats,
    UserUpdate,
)
from app.schemas.auth import ScopeOut
from app.schemas.reference import (
    DistrictOut,
    EAOut,
    EnumeratorOut,
    PickListIn,
    PickListOut,
    RegionOut,
    SupervisorOut,
    TeamOut,
)
from app.services import import_service, permission_service
from app.services.reference import current_settings

router = APIRouter(prefix="/admin", tags=["admin"])

manage_users = require_perm("users.manage")
manage_roles = require_perm("roles.manage")
manage_devices = require_perm("devices.manage")
manage_reference = require_perm("reference.manage")
manage_settings = require_perm("settings.manage")
view_audit = require_perm("audit.view")


def _user_out(u: User) -> UserAdminOut:
    out = UserAdminOut.model_validate(u)
    out.scopes = [ScopeOut(region_id=s.region_id, district_id=s.district_id) for s in u.scopes]
    return out


def _set_scopes(db: Session, user: User, district_ids: list[int], region_ids: list[int]):
    user.scopes.clear()
    for d in district_ids:
        if db.get(District, d) is None:
            raise HTTPException(400, f"Unknown district id {d}")
        user.scopes.append(UserScope(district_id=d))
    for r in region_ids:
        if db.get(Region, r) is None:
            raise HTTPException(400, f"Unknown region id {r}")
        user.scopes.append(UserScope(region_id=r))


# ---- Users -----------------------------------------------------------------


@router.get("/users", response_model=list[UserAdminOut])
def list_users(
    search: str | None = None,
    role: Role | None = None,
    district_id: int | None = None,
    region_id: int | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(manage_users),
):
    q = select(User).options(selectinload(User.scopes)).order_by(User.full_name)
    if search:
        like = f"%{search.strip()}%"
        q = q.where(User.full_name.ilike(like) | User.username.ilike(like) | User.phone.ilike(like))
    if role:
        q = q.where(User.role == role)
    if active is not None:
        q = q.where(User.active == active)
    users = db.execute(q).scalars().all()
    if district_id or region_id:
        def in_scope(u: User) -> bool:
            if u.role in (Role.NATIONAL_DQM, Role.ADMIN):
                return False
            for s in u.scopes:
                if district_id and s.district_id == district_id:
                    return True
                if region_id and (s.region_id == region_id or (s.district_id and (d := db.get(District, s.district_id)) and d.region_id == region_id)):
                    return True
            return False
        users = [u for u in users if in_scope(u)]
    return [_user_out(u) for u in users]


@router.get("/users/stats", response_model=UserStats)
def user_stats(db: Session = Depends(get_db), _: User = Depends(manage_users)):
    users = db.execute(select(User)).scalars().all()
    now = datetime.now(timezone.utc)
    by_role: dict[str, int] = {r.value: 0 for r in Role}
    for u in users:
        by_role[u.role.value] += 1
    return UserStats(
        total=len(users), active=sum(1 for u in users if u.active), inactive=sum(1 for u in users if not u.active), by_role=by_role,
        locked=sum(1 for u in users if u.locked_until and u.locked_until.replace(tzinfo=u.locked_until.tzinfo or timezone.utc) > now),
        never_logged_in=sum(1 for u in users if u.last_login_at is None),
    )


@router.get("/users/template.csv")
def users_template(_: User = Depends(manage_users)):
    from fastapi.responses import PlainTextResponse

    body = (
        "username,password,full_name,phone,role,districts,region\n"
        "dqm.bo,ChangeMe123,District DQM Bo,+23276000000,DISTRICT_DQM,Bo,\n"
        "regional.south,ChangeMe123,Regional Officer Southern,,REGIONAL,,Southern\n"
        "fm.bo.1,ChangeMe123,Field Monitor Bo 1,+23277000000,FIELD_MONITOR,Bo,\n"
    )
    return PlainTextResponse(body, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="users-template.csv"'})


@router.post("/users/import", response_model=UserImportResult)
async def import_users(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), admin: User = Depends(manage_users)):
    import csv
    import io

    content = (await file.read()).decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(content)))
    districts = {d.name.lower(): d for d in db.execute(select(District)).scalars()}
    districts.update({d.code.lower(): d for d in districts.values()})
    regions = {r.name.lower(): r for r in db.execute(select(Region)).scalars()}
    created, skipped, errors, names = 0, 0, [], []
    for i, row in enumerate(rows, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        username = row.get("username", "").lower()
        if not username:
            errors.append(f"Row {i}: username missing")
            continue
        if db.execute(select(User).where(User.username == username)).scalars().first():
            skipped += 1
            continue
        try:
            role = Role(row.get("role", "").upper())
        except ValueError:
            errors.append(f"Row {i}: unknown role '{row.get('role')}'")
            continue
        password = row.get("password") or secrets.token_urlsafe(9)
        if len(password) < 8:
            errors.append(f"Row {i}: password shorter than 8 characters")
            continue
        user = User(username=username, password_hash=hash_password(password), full_name=row.get("full_name") or username, phone=row.get("phone") or None, role=role)
        bad = False
        for name in filter(None, (x.strip() for x in row.get("districts", "").replace(";", ",").split(","))):
            d = districts.get(name.lower())
            if d is None:
                errors.append(f"Row {i}: unknown district '{name}'")
                bad = True
                break
            user.scopes.append(UserScope(district_id=d.id))
        if bad:
            continue
        if row.get("region"):
            r = regions.get(row["region"].lower())
            if r is None:
                errors.append(f"Row {i}: unknown region '{row['region']}'")
                continue
            user.scopes.append(UserScope(region_id=r.id))
        db.add(user)
        db.flush()
        created += 1
        names.append(username)
    audit(db, admin, "user.import", "file", file.filename, {"created": created, "skipped": skipped, "errors": len(errors), "users": names}, request)
    db.commit()
    return UserImportResult(created=created, skipped=skipped, errors=errors[:100], created_users=names)


@router.post("/users/{user_id}/reset-pin", response_model=PinResetOut)
def reset_pin(user_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_users)):
    """Ask a Field Monitor's tablet to forget its PIN.

    The tablet picks the request up at its next sync (or as soon as its session token can no
    longer be refreshed), wipes the PIN and the session, keeps the records, and shows the
    sign-in screen. The monitor signs in again with the password and chooses a new PIN, which
    clears the request. Reset the password first if the monitor has forgotten that too."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.role != Role.FIELD_MONITOR:
        raise HTTPException(400, "Only Field Monitor accounts use a tablet PIN")
    user.pin_reset_requested_at = datetime.now(timezone.utc)
    for t in db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))).scalars():
        t.revoked = True  # the tablet must sign in again even if it misses the sync flag
    audit(db, admin, "user.reset_pin", "user", user.id, {"username": user.username}, request)
    db.commit()
    return PinResetOut(user_id=user.id, username=user.username, pin_reset_requested_at=user.pin_reset_requested_at)


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetOut)
def reset_password(user_id: int, body: PasswordResetIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_users)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    temp = None
    password = body.password
    if not password:
        temp = password = secrets.token_urlsafe(9)
    user.password_hash = hash_password(password)
    user.failed_logins = 0
    user.locked_until = None
    for t in db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))).scalars():
        t.revoked = True  # sign the user out everywhere
    audit(db, admin, "user.reset_password", "user", user.id, {"username": user.username, "generated": temp is not None}, request)
    db.commit()
    return PasswordResetOut(user_id=user.id, username=user.username, temporary_password=temp)


@router.post("/users/{user_id}/deactivate", response_model=UserAdminOut)
def deactivate_user(user_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_users)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id:
        raise HTTPException(400, "You cannot deactivate your own account")
    user.active = False
    for t in db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False))).scalars():
        t.revoked = True
    audit(db, admin, "user.deactivate", "user", user.id, {"username": user.username}, request)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.post("/users/{user_id}/activate", response_model=UserAdminOut)
def activate_user(user_id: int, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_users)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    user.active = True
    user.failed_logins = 0
    user.locked_until = None
    audit(db, admin, "user.activate", "user", user.id, {"username": user.username}, request)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.get("/users/{user_id}/activity", response_model=UserActivity)
def user_activity(user_id: int, db: Session = Depends(get_db), _: User = Depends(manage_users)):
    user = db.execute(select(User).options(selectinload(User.scopes)).where(User.id == user_id)).scalars().first()
    if user is None:
        raise HTTPException(404, "User not found")
    devices = []
    for d in db.execute(select(Device).where(Device.user_id == user_id).order_by(Device.last_sync_at.desc().nullslast())).scalars():
        o = DeviceOut.model_validate(d)
        o.username, o.full_name = user.username, user.full_name
        devices.append(o)
    recent = []
    for a in db.execute(select(AuditLog).where(AuditLog.user_id == user_id).order_by(AuditLog.at.desc()).limit(50)).scalars():
        o = AuditOut.model_validate(a)
        o.user_name, o.username = user.full_name, user.username
        recent.append(o)
    counts = {
        "errors_logged": db.execute(select(func.count()).select_from(ErrorRecord).where(ErrorRecord.user_id == user_id)).scalar_one(),
        "daily_reports": db.execute(select(func.count()).select_from(DqmDailyReport).where(DqmDailyReport.created_by == user_id)).scalar_one(),
        "checkouts": db.execute(select(func.count()).select_from(ExitCheckout).where(ExitCheckout.created_by == user_id)).scalar_one(),
        "logins": db.execute(select(func.count()).select_from(AuditLog).where(AuditLog.user_id == user_id, AuditLog.action == "auth.login")).scalar_one(),
    }
    return UserActivity(user=_user_out(user), devices=devices, recent=recent, counts=counts)


@router.post("/users", response_model=UserAdminOut, status_code=201)
def create_user(body: UserCreate, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_users)):
    username = body.username.strip().lower()
    if db.execute(select(User).where(User.username == username)).scalars().first():
        raise HTTPException(409, "Username already exists")
    user = User(username=username, password_hash=hash_password(body.password), full_name=body.full_name, phone=body.phone, role=body.role)
    db.add(user)
    db.flush()
    _set_scopes(db, user, body.district_ids, body.region_ids)
    audit(db, admin, "user.create", "user", user.id, {"username": username, "role": body.role, "district_ids": body.district_ids, "region_ids": body.region_ids}, request)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.patch("/users/{user_id}", response_model=UserAdminOut)
def update_user(user_id: int, body: UserUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_users)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    before = snapshot(user)
    before_scopes = sorted((s.region_id, s.district_id) for s in user.scopes)
    for field in ("full_name", "phone", "role", "active"):
        value = getattr(body, field)
        if value is not None:
            setattr(user, field, value)
    if body.password:
        user.password_hash = hash_password(body.password)
        user.failed_logins = 0
        user.locked_until = None
    if body.district_ids is not None or body.region_ids is not None:
        _set_scopes(db, user, body.district_ids or [], body.region_ids or [])
    after_scopes = sorted((s.region_id, s.district_id) for s in user.scopes)
    changes = diff(before, snapshot(user), ignore=("updated_at", "password_hash", "failed_logins", "locked_until"))
    if body.password:
        changes["password"] = ["***", "reset"]
    if before_scopes != after_scopes:
        changes["scopes"] = [before_scopes, after_scopes]
    audit(db, admin, "user.update", "user", user.id, {"username": user.username, "changes": changes}, request)
    db.commit()
    db.refresh(user)
    return _user_out(user)


# ---- Roles and permissions ---------------------------------------------------


@router.get("/permissions", response_model=list[PermissionInfo])
def permissions(_: User = Depends(require_web)):
    return [PermissionInfo(code=c, group=g, description=d) for c, (g, d) in PERMISSIONS.items()]


@router.get("/roles", response_model=RoleMatrix)
def roles(db: Session = Depends(get_db), _: User = Depends(manage_roles)):
    return RoleMatrix(
        roles=permission_service.role_matrix(db),
        defaults={r.value: sorted(c) for r, c in DEFAULT_ROLE_PERMISSIONS.items()},
        permissions=[PermissionInfo(code=c, group=g, description=d) for c, (g, d) in PERMISSIONS.items()],
    )


@router.put("/roles/{role}", response_model=RoleMatrix)
def set_role(role: Role, body: RolePermissionsIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_roles)):
    if role == Role.ADMIN and admin.role == Role.ADMIN and ("roles.manage" not in body.codes or "users.manage" not in body.codes):
        raise HTTPException(400, "The Administrator role must keep users.manage and roles.manage")
    before = sorted(permission_service.role_permissions(db, role))
    try:
        after = permission_service.set_role_permissions(db, role, body.codes)
    except ValueError as e:
        raise HTTPException(400, str(e))
    audit(db, admin, "role.permissions", "role", role.value, {"added": sorted(set(after) - set(before)), "removed": sorted(set(before) - set(after))}, request)
    db.commit()
    return roles(db, admin)


@router.get("/users/{user_id}/permissions", response_model=UserPermissionsOut)
def user_permissions(user_id: int, db: Session = Depends(get_db), _: User = Depends(manage_roles)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    overrides = permission_service.user_overrides(db, user_id)
    return UserPermissionsOut(
        user_id=user_id, role=user.role, role_codes=sorted(permission_service.role_permissions(db, user.role)),
        grant=sorted(c for c, g in overrides.items() if g), revoke=sorted(c for c, g in overrides.items() if not g),
        effective=sorted(permission_service.effective_permissions(db, user)),
    )


@router.put("/users/{user_id}/permissions", response_model=UserPermissionsOut)
def set_user_permissions(user_id: int, body: UserPermissionsIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_roles)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id and "roles.manage" in body.revoke:
        raise HTTPException(400, "You cannot revoke your own roles.manage right")
    before = permission_service.user_overrides(db, user_id)
    try:
        after = permission_service.set_user_overrides(db, user_id, body.grant, body.revoke)
    except ValueError as e:
        raise HTTPException(400, str(e))
    audit(db, admin, "user.permissions", "user", user_id, {"username": user.username, "before": before, "after": after}, request)
    db.commit()
    return user_permissions(user_id, db, admin)


# ---- Devices ---------------------------------------------------------------


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db), _: User = Depends(require_web)):
    rows = db.execute(select(Device, User).join(User, User.id == Device.user_id).order_by(Device.last_sync_at.desc().nullslast())).all()
    out = []
    for device, user in rows:
        d = DeviceOut.model_validate(device)
        d.username = user.username
        d.full_name = user.full_name
        out.append(d)
    return out


@router.patch("/devices/{device_id}", response_model=DeviceOut)
def set_device_status(device_id: str, body: DeviceStatusUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_devices)):
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    previous = device.status
    device.status = body.status
    audit(db, admin, "device.status", "device", device_id, {"from": previous, "to": body.status, "model": device.model}, request)
    db.commit()
    db.refresh(device)
    user = db.get(User, device.user_id)
    d = DeviceOut.model_validate(device)
    d.username = user.username if user else None
    d.full_name = user.full_name if user else None
    return d


# ---- Reference lists -------------------------------------------------------


@router.get("/reference/regions", response_model=list[RegionOut])
def regions(db: Session = Depends(get_db), _: User = Depends(require_web)):
    return db.execute(select(Region).order_by(Region.name)).scalars().all()


@router.get("/reference/districts", response_model=list[DistrictOut])
def districts(db: Session = Depends(get_db), _: User = Depends(require_web)):
    return db.execute(select(District).order_by(District.name)).scalars().all()


@router.get("/reference/teams", response_model=list[TeamOut])
def teams(district_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(require_web)):
    q = select(Team).order_by(Team.code)
    if district_id:
        q = q.where(Team.district_id == district_id)
    return db.execute(q).scalars().all()


@router.get("/reference/supervisors", response_model=list[SupervisorOut])
def supervisors(team_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(require_web)):
    q = select(Supervisor).order_by(Supervisor.name)
    if team_id:
        q = q.where(Supervisor.team_id == team_id)
    return db.execute(q).scalars().all()


@router.get("/reference/enumerators", response_model=list[EnumeratorOut])
def enumerators(team_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(require_web)):
    q = select(Enumerator).order_by(Enumerator.name)
    if team_id:
        q = q.where(Enumerator.team_id == team_id)
    return db.execute(q).scalars().all()


@router.get("/reference/eas", response_model=list[EAOut])
def eas(team_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(require_web)):
    q = select(EnumerationArea).order_by(EnumerationArea.code)
    if team_id:
        q = q.where(EnumerationArea.team_id == team_id)
    return db.execute(q).scalars().all()


@router.get("/reference/categories", response_model=list[PickListOut])
def categories(db: Session = Depends(get_db), _: User = Depends(require_web)):
    return db.execute(select(ErrorCategory).order_by(ErrorCategory.sort_order, ErrorCategory.name)).scalars().all()


@router.get("/reference/sources", response_model=list[PickListOut])
def sources(db: Session = Depends(get_db), _: User = Depends(require_web)):
    return db.execute(select(ErrorSource).order_by(ErrorSource.sort_order, ErrorSource.name)).scalars().all()


def _upsert_picklist(db: Session, model, body: PickListIn, admin: User, item_id: int | None, request: Request):
    if item_id is None:
        if db.execute(select(model).where(model.code == body.code)).scalars().first():
            raise HTTPException(409, "Code already exists")
        row = model(**body.model_dump())
        db.add(row)
        audit(db, admin, f"{model.__tablename__}.create", model.__tablename__, body.code, body.model_dump(), request)
    else:
        row = db.get(model, item_id)
        if row is None:
            raise HTTPException(404, "Not found")
        before = snapshot(row)
        for k, v in body.model_dump().items():
            setattr(row, k, v)
        audit(db, admin, f"{model.__tablename__}.update", model.__tablename__, body.code, {"changes": diff(before, snapshot(row))}, request)
    db.commit()
    db.refresh(row)
    return row


@router.post("/reference/categories", response_model=PickListOut, status_code=201)
def create_category(body: PickListIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_reference)):
    return _upsert_picklist(db, ErrorCategory, body, admin, None, request)


@router.put("/reference/categories/{item_id}", response_model=PickListOut)
def update_category(item_id: int, body: PickListIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_reference)):
    return _upsert_picklist(db, ErrorCategory, body, admin, item_id, request)


@router.post("/reference/sources", response_model=PickListOut, status_code=201)
def create_source(body: PickListIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_reference)):
    return _upsert_picklist(db, ErrorSource, body, admin, None, request)


@router.put("/reference/sources/{item_id}", response_model=PickListOut)
def update_source(item_id: int, body: PickListIn, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_reference)):
    return _upsert_picklist(db, ErrorSource, body, admin, item_id, request)


@router.post("/reference/import", response_model=ImportResult)
async def import_reference(
    request: Request,
    file: UploadFile = File(...),
    region: str | None = Query(default=None, description="Region name to use when the file has no region column"),
    db: Session = Depends(get_db),
    admin: User = Depends(manage_reference),
):
    content = await file.read()
    if len(content) > 250 * 1024 * 1024:
        raise HTTPException(413, "File larger than 250 MB")
    result = import_service.import_reference(db, file.filename or "import.csv", content, region)
    audit(db, admin, "reference.import", "file", file.filename, f"rows={result.rows} teams={result.teams} eas={result.eas}", request)
    db.commit()
    return result


# ---- Settings and audit ----------------------------------------------------


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), _: User = Depends(require_web)):
    return current_settings(db)


@router.put("/settings")
def put_settings(body: SettingsUpdate, request: Request, db: Session = Depends(get_db), admin: User = Depends(manage_settings)):
    before = current_settings(db)
    for key, value in body.model_dump(exclude_none=True).items():
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=str(value)))
        else:
            row.value = str(value)
    db.flush()
    audit(db, admin, "settings.update", "setting", None, {"changes": diff(before, current_settings(db))}, request)
    db.commit()
    return current_settings(db)


@router.get("/audit", response_model=list[AuditOut])
def audit_log(
    user_id: int | None = None,
    action: str | None = None,
    entity: str | None = None,
    entity_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=200, le=2000),
    db: Session = Depends(get_db),
    _: User = Depends(view_audit),
):
    q = select(AuditLog, User).outerjoin(User, User.id == AuditLog.user_id).order_by(AuditLog.at.desc())
    if user_id:
        q = q.where(AuditLog.user_id == user_id)
    if action:
        q = q.where(AuditLog.action.ilike(f"{action}%"))
    if entity:
        q = q.where(AuditLog.entity == entity)
    if entity_id:
        q = q.where(AuditLog.entity_id == entity_id)
    if date_from:
        q = q.where(AuditLog.at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        q = q.where(AuditLog.at <= datetime.combine(date_to, time.max, tzinfo=timezone.utc))
    out = []
    for row, user in db.execute(q.limit(limit)):
        a = AuditOut.model_validate(row)
        a.user_name = user.full_name if user else None
        a.username = user.username if user else None
        out.append(a)
    return out


@router.get("/audit/actions", response_model=list[str])
def audit_actions(db: Session = Depends(get_db), _: User = Depends(view_audit)):
    return sorted({a for (a,) in db.execute(select(AuditLog.action).distinct())})
