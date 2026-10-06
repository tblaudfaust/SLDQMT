"""Clear the operational data before go-live, keeping the reference frames and the admin accounts.

    python -m scripts.reset_operational_data --yes            # records, reports, devices, audit trail
    python -m scripts.reset_operational_data --yes --users    # ...and every non-ADMIN account

Deleted with --yes: error records, follow-ups, activity, exit check-outs, daily DQM
reports, sync logs, registered devices, refresh tokens and the audit log.
Kept: regions, districts, SAs, supervisors, enumerators, EAs, error categories and
sources, settings, roles and rights, and the ADMIN accounts (plus every other account
unless --users is given, which also removes their scopes, devices and permissions).

On the VPS:
    docker compose -f docker-compose.prod.yml exec server python -m scripts.reset_operational_data --yes --users
"""

import sys

from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models import (
    Activity,
    AuditLog,
    Device,
    DqmDailyReport,
    ErrorRecord,
    ExitCheckout,
    FollowUp,
    RefreshToken,
    SyncLog,
    User,
    UserPermission,
    UserScope,
)
from app.models.user import Role

OPERATIONAL = [FollowUp, Activity, ErrorRecord, ExitCheckout, DqmDailyReport, SyncLog, Device, RefreshToken, AuditLog]


def main(argv: list[str]) -> None:
    if "--yes" not in argv:
        print(__doc__)
        print("Nothing deleted: add --yes to confirm.")
        sys.exit(1)
    remove_users = "--users" in argv
    db = SessionLocal()
    try:
        for model in OPERATIONAL:
            n = db.execute(select(func.count()).select_from(model)).scalar_one()
            db.execute(delete(model))
            print(f"{model.__tablename__:18s} deleted {n}")
        if remove_users:
            ids = db.execute(select(User.id).where(User.role != Role.ADMIN)).scalars().all()
            if ids:
                db.execute(delete(UserPermission).where(UserPermission.user_id.in_(ids)))
                db.execute(delete(UserScope).where(UserScope.user_id.in_(ids)))
                db.execute(delete(User).where(User.id.in_(ids)))
            print(f"{'user':18s} deleted {len(ids)} non-admin accounts")
        db.commit()
        print("Done. Reference frames, settings, roles and admin accounts were kept.")
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1:])
