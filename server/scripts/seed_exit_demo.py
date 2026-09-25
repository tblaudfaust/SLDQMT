"""Seed demo Field Exit Protocol check-outs (a handful per district) so the
exit summary pages have something to show.

    python -m scripts.seed_exit_demo
"""

import json
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models import CheckoutStatus, ClearanceDecision, District, Enumerator, ExitCheckout, StaffRole, Supervisor, Team, User
from app.models.user import Role

random.seed(23)


def main():
    db = SessionLocal()
    init_db(db)
    if db.query(ExitCheckout).count():
        print("Exit check-outs already seeded")
        return
    national = db.execute(select(User).where(User.role == Role.NATIONAL_DQM)).scalars().first()
    created = 0
    now = datetime.now(timezone.utc)
    for d in db.execute(select(District).order_by(District.name)).scalars():
        officer = db.execute(select(User).where(User.username == "dqm." + "".join(c for c in d.name.lower() if c.isalnum())[:12])).scalars().first()
        teams = db.execute(select(Team).where(Team.district_id == d.id).limit(4)).scalars().all()
        for t in teams:
            people = [(s.name, s.code, StaffRole.SUPERVISOR) for s in db.execute(select(Supervisor).where(Supervisor.team_id == t.id)).scalars()]
            people += [(e.name, e.code, StaffRole.ENUMERATOR) for e in db.execute(select(Enumerator).where(Enumerator.team_id == t.id).limit(3)).scalars()]
            for name, code, role in people:
                fails = random.sample(range(1, 13), k=random.choice([0, 0, 1, 2]))
                checklist = [{"n": n, "answer": "NO" if n in fails else "YES", "remarks": "Pending" if n in fails else ""} for n in range(1, 13)]
                items = [{"item": c, "returned": random.random() > 0.08, "condition": "Good", "clearance": ""} for c in ("FINAL_SYNC", "NO_UNSYNCED", "TABLET", "POWER_SIM", "ID_LETTER", "SD_CARD", "PARADATA")]
                stage = random.choices(["DRAFT", "SUBMITTED", "NATIONAL_SIGNED", "CLEARED"], [1, 2, 2, 5])[0]
                r = ExitCheckout(
                    district_id=d.id, team_id=t.id, staff_name=name, login_id=code, role=role, sa_ea_codes=t.code,
                    checklist=json.dumps(checklist), items=json.dumps(items), approvals="[]",
                    status=CheckoutStatus(stage), created_by=(officer or national).id,
                    enumerator_conduct="Good conduct" if role == StaffRole.ENUMERATOR else None,
                )
                if stage != "DRAFT":
                    r.submitted_by = (officer or national).id
                    r.submitted_at = now - timedelta(days=random.randint(1, 6))
                    r.approvals = json.dumps([{"role": "DISTRICT_DQM", "name": (officer or national).full_name, "comment": "", "signed_on": r.submitted_at.date().isoformat()}])
                if stage in ("NATIONAL_SIGNED", "CLEARED") and national:
                    r.national_signed_by = national.id
                    r.national_signed_name = national.full_name
                    r.national_signed_at = r.submitted_at + timedelta(hours=8)
                if stage == "CLEARED":
                    problems = bool(fails) or any(not i["returned"] for i in items)
                    r.decision = random.choice([ClearanceDecision.CONDITIONAL, ClearanceDecision.NOT_CLEARED]) if problems else random.choice([ClearanceDecision.CLEARED_PAYMENT, ClearanceDecision.CLEARED_PAYMENT, ClearanceDecision.CLEARED_REDEPLOYMENT])
                    if r.decision in (ClearanceDecision.CONDITIONAL, ClearanceDecision.NOT_CLEARED):
                        r.outstanding_issues = "Resolve checklist items " + ", ".join(map(str, fails)) if fails else "Return missing items"
                        r.deadline = date.today() + timedelta(days=random.randint(-3, 10))
                    r.decided_name = "Director, Data Science Division"
                    r.decided_by = national.id if national else None
                    r.decided_at = r.national_signed_at + timedelta(days=1)
                db.add(r)
                created += 1
    db.commit()
    print(f"Seeded {created} exit check-outs")


if __name__ == "__main__":
    main()
