"""Seed demo users and a spread of demo errors so the dashboard has something
to show.

    python -m scripts.seed_demo

If the reference tables already hold real geography (from
`scripts.import_frames`), the demo uses the first three districts of it.
Otherwise it creates a small fake hierarchy first. Demo users are created
with password Password123: one Field Monitor per demo district (fm.<code>),
dqm.<code> for the first district, regional.<code> for its region, and
dqm.national. Re-running adds nothing when the demo users already exist.
"""

import random
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models import (
    Activity,
    Device,
    District,
    Enumerator,
    EnumerationArea,
    ErrorCategory,
    ErrorRecord,
    ErrorSource,
    ErrorStatus,
    FollowUp,
    Region,
    Role,
    Supervisor,
    SupportMethod,
    Team,
    User,
    UserScope,
)
from app.services.followup import load_policy, next_follow_up

FAKE_GEO = {
    "Western": {"WAU": "Western Area Urban", "WAR": "Western Area Rural"},
    "Northern": {"BOM": "Bombali"},
}


def slug(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())[:12]


def ensure_fake_geography(db) -> None:
    if db.query(Region).count():
        return
    for rname, dists in FAKE_GEO.items():
        r = Region(code=rname[:3].upper(), name=rname)
        db.add(r)
        db.flush()
        for code, name in dists.items():
            d = District(region_id=r.id, code=code, name=name)
            db.add(d)
            db.flush()
            for n in range(1, 4):
                t = Team(district_id=d.id, code=f"{d.code}-SA{n:02d}", name=f"{d.name} SA {n}", chiefdom=f"Chiefdom {n}")
                db.add(t)
                db.flush()
                db.add(Supervisor(team_id=t.id, code=f"S{t.id}", name=f"Supervisor {d.code}{n}", phone=f"+2327{random.randint(1000000, 9999999)}"))
                for e in range(1, 5):
                    db.add(Enumerator(team_id=t.id, code=f"E{t.id}{e}", name=f"Enumerator {d.code}{n}-{e}"))
                for ea in range(1, 4):
                    db.add(EnumerationArea(team_id=t.id, code=f"{t.code}-EA{ea:02d}", name=f"Locality {ea}"))
    db.flush()


def main():
    random.seed(7)
    db = SessionLocal()
    init_db(db)
    if db.execute(select(User).where(User.username == "dqm.national")).scalars().first():
        print("Demo users already exist; nothing to do")
        return
    ensure_fake_geography(db)
    now = datetime.now(timezone.utc)
    policy = load_policy(db)

    districts = db.execute(select(District).order_by(District.name)).scalars().all()[:3]
    if not districts:
        print("No districts found")
        return

    monitors = []
    for d in districts:
        u = User(username=f"fm.{slug(d.name)}", password_hash=hash_password("Password123"), full_name=f"Field Monitor {d.name}", role=Role.FIELD_MONITOR)
        u.scopes.append(UserScope(district_id=d.id))
        db.add(u)
        db.flush()
        dev = Device(id=str(uuid.uuid4()), user_id=u.id, model="Samsung SM-T510", android_version="13", app_version="0.1.0", last_sync_at=now - timedelta(hours=random.randint(1, 30)))
        db.add(dev)
        monitors.append((u, dev, d))

    first = districts[0]
    ddqm = User(username=f"dqm.{slug(first.name)}", password_hash=hash_password("Password123"), full_name=f"District DQM {first.name}", role=Role.DISTRICT_DQM)
    ddqm.scopes.append(UserScope(district_id=first.id))
    db.add(ddqm)
    region = db.get(Region, first.region_id)
    reg = User(username=f"regional.{slug(region.name)}", password_hash=hash_password("Password123"), full_name=f"Regional Officer {region.name}", role=Role.REGIONAL)
    reg.scopes.append(UserScope(region_id=region.id))
    db.add(reg)
    db.add(User(username="dqm.national", password_hash=hash_password("Password123"), full_name="National DQM", role=Role.NATIONAL_DQM))
    db.flush()

    cats = db.query(ErrorCategory).all()
    sources = db.query(ErrorSource).all()
    seq = 0
    for u, dev, d in monitors:
        d_teams = db.execute(select(Team).where(Team.district_id == d.id).limit(6)).scalars().all()
        if not d_teams:
            continue
        for _ in range(random.randint(18, 30)):
            seq += 1
            t = random.choice(d_teams)
            sup = db.execute(select(Supervisor).where(Supervisor.team_id == t.id)).scalars().first()
            enums = db.execute(select(Enumerator).where(Enumerator.team_id == t.id)).scalars().all()
            eas = db.execute(select(EnumerationArea).where(EnumerationArea.team_id == t.id)).scalars().all()
            enum = random.choice(enums) if enums else None
            ea = random.choice(eas) if eas else None
            received = date.today() - timedelta(days=random.randint(0, 20))
            created = datetime.combine(received, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=random.randint(8, 17))
            resolved = random.random() < 0.55
            last_action = min(created + timedelta(hours=random.randint(1, 72)), now - timedelta(minutes=30))
            cat = random.choice(cats)
            e = ErrorRecord(
                id=str(uuid.uuid4()),
                display_id=f"FM-{d.code}-{received.strftime('%y%m')}-{seq:04d}",
                user_id=u.id,
                device_id=dev.id,
                district_id=d.id,
                team_id=t.id,
                supervisor_id=sup.id if sup else None,
                supervisor_name=sup.name if sup else "Supervisor",
                enumerator_id=enum.id if enum else None,
                enumerator_name=enum.name if enum else None,
                ea_id=ea.id if ea else None,
                category_id=cat.id,
                source_id=random.choice(sources).id,
                description=f"{cat.name} reported by DQM for household {random.randint(1, 60)} in {ea.locality or ea.code if ea else t.name}",
                date_received=received,
                support_method=random.choice(list(SupportMethod)),
                action_taken="Called supervisor and explained the correction needed",
                status=ErrorStatus.RESOLVED if resolved else ErrorStatus.UNRESOLVED,
                resolved_at=last_action if resolved else None,
                last_action_at=last_action,
                next_follow_up_at=None if resolved else next_follow_up(last_action, policy),
                lat=(ea.lat if ea and ea.lat else 8.48 + random.random() * 0.5),
                lng=(ea.lng if ea and ea.lng else -13.23 + random.random() * 0.5),
                accuracy_m=random.choice([8, 12, 25, 40]),
                gps_at=created,
                client_created_at=created,
                client_updated_at=last_action,
            )
            db.add(e)
            db.add(Activity(id=str(uuid.uuid4()), error_id=e.id, user_id=u.id, device_id=dev.id, previous_status=None, new_status=ErrorStatus.UNRESOLVED, action_taken=e.action_taken, client_at=created))
            for k in range(random.randint(0, 2)):
                at = created + timedelta(hours=4 * (k + 1))
                if at < now:
                    db.add(FollowUp(id=str(uuid.uuid4()), error_id=e.id, user_id=u.id, device_id=dev.id, at=at, method=SupportMethod.REMOTE, contacted=e.supervisor_name, outcome="Supervisor confirmed enumerator will correct", client_created_at=at))
            if resolved:
                db.add(Activity(id=str(uuid.uuid4()), error_id=e.id, user_id=u.id, device_id=dev.id, previous_status=ErrorStatus.UNRESOLVED, new_status=ErrorStatus.RESOLVED, action_taken="Correction confirmed in CSPro", client_at=last_action))
    db.commit()
    names = ", ".join(f"fm.{slug(d.name)}" for d in districts)
    print(f"Seeded demo data. Logins (password Password123): {names}, dqm.{slug(first.name)}, regional.{slug(region.name)}, dqm.national; admin / change-me-immediately")


if __name__ == "__main__":
    main()
