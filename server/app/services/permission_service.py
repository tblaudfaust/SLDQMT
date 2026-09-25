"""Effective permissions = the role's rights, plus per-user grants, minus
per-user revocations. One helper computes it everywhere a right is checked
or reported, so an override behaves identically on every path."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSIONS
from app.models import RolePermission, User, UserPermission
from app.models.user import Role


def role_permissions(db: Session, role: Role) -> set[str]:
    rows = db.execute(select(RolePermission.code).where(RolePermission.role == role)).scalars().all()
    return set(rows)


def role_matrix(db: Session) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {r.value: [] for r in Role}
    for rp in db.execute(select(RolePermission)).scalars():
        out[rp.role.value].append(rp.code)
    for k in out:
        out[k].sort()
    return out


def set_role_permissions(db: Session, role: Role, codes: list[str]) -> list[str]:
    unknown = sorted(set(codes) - set(PERMISSIONS))
    if unknown:
        raise ValueError(f"Unknown permission(s): {', '.join(unknown)}")
    current = role_permissions(db, role)
    wanted = set(codes)
    for code in current - wanted:
        db.execute(select(RolePermission).where(RolePermission.role == role, RolePermission.code == code))
        for rp in db.execute(select(RolePermission).where(RolePermission.role == role, RolePermission.code == code)).scalars():
            db.delete(rp)
    for code in wanted - current:
        db.add(RolePermission(role=role, code=code))
    db.flush()
    return sorted(wanted)


def user_overrides(db: Session, user_id: int) -> dict[str, bool]:
    return {up.code: up.granted for up in db.execute(select(UserPermission).where(UserPermission.user_id == user_id)).scalars()}


def set_user_overrides(db: Session, user_id: int, grant: list[str], revoke: list[str]) -> dict[str, bool]:
    unknown = sorted((set(grant) | set(revoke)) - set(PERMISSIONS))
    if unknown:
        raise ValueError(f"Unknown permission(s): {', '.join(unknown)}")
    for up in db.execute(select(UserPermission).where(UserPermission.user_id == user_id)).scalars():
        db.delete(up)
    db.flush()
    for code in set(grant):
        db.add(UserPermission(user_id=user_id, code=code, granted=True))
    for code in set(revoke) - set(grant):
        db.add(UserPermission(user_id=user_id, code=code, granted=False))
    db.flush()
    return user_overrides(db, user_id)


def effective_permissions(db: Session, user: User) -> set[str]:
    perms = role_permissions(db, user.role)
    if not perms and not db.execute(select(RolePermission.id).limit(1)).first():
        # Table not seeded yet (fresh database): fall back to the defaults.
        perms = set(DEFAULT_ROLE_PERMISSIONS.get(user.role, []))
    for code, granted in user_overrides(db, user.id).items():
        if granted:
            perms.add(code)
        else:
            perms.discard(code)
    return perms


def seed_defaults(db: Session) -> None:
    if db.execute(select(RolePermission.id).limit(1)).first():
        return
    for role, codes in DEFAULT_ROLE_PERMISSIONS.items():
        for code in codes:
            db.add(RolePermission(role=role, code=code))
    db.flush()
