"""Seed demo Annex A daily reports for the last 10 days across every district
(and a District DQM user per district) so the DQM analytics pages have
something to show. Skips district-days that already have a report.

    python -m scripts.seed_dqm_demo
"""

import json
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models import District, DqmDailyReport, Region, ReportPeriod, ReportStatus, Role, Team, User, UserScope

random.seed(11)


def slug(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum())[:12]


def main():
    db = SessionLocal()
    init_db(db)
    if db.execute(select(Region)).scalars().first() is None:
        print("No geography loaded; run scripts.import_frames first")
        return
    districts = db.execute(select(District).order_by(District.name)).scalars().all()
    national = db.execute(select(User).where(User.role == Role.NATIONAL_DQM)).scalars().first()
    today = date.today()
    created = 0
    for d in districts:
        username = f"dqm.{slug(d.name)}"
        user = db.execute(select(User).where(User.username == username)).scalars().first()
        if user is None:
            user = User(username=username, password_hash=hash_password("Password123"), full_name=f"District DQM {d.name}", role=Role.DISTRICT_DQM)
            user.scopes.append(UserScope(district_id=d.id))
            db.add(user)
            db.flush()
        teams = db.execute(select(Team).where(Team.district_id == d.id).limit(8)).scalars().all()
        reviewed = 0
        certified = 0
        skip_prob = random.choice([0.0, 0.1, 0.3])
        for back in range(10, -1, -1):
            day = today - timedelta(days=back)
            if db.execute(select(DqmDailyReport).where(DqmDailyReport.district_id == d.id, DqmDailyReport.report_date == day)).scalars().first():
                continue
            if random.random() < skip_prob and back > 0:
                continue
            reviewed += random.randint(2, 6)
            certified += random.randint(1, 4)
            certified = min(certified, reviewed)
            errors = [
                {"band": random.choices(["LOW", "MEDIUM", "HIGH"], [5, 3, 1])[0], "ea_code": f"{t.code}{random.randint(1, 5):02d}", "team": t.code, "likely_cause": random.choice(["Skip pattern", "Age mis-recorded", "Household member omitted"]), "correction": "Coaching by supervisor", "remarks": ""}
                for t in random.sample(teams, k=min(len(teams), random.randint(0, 4)))
            ]
            issues = [
                {"issue_type": random.choice(["OUTLIER", "GPS", "SYNC"]), "ea_code": f"{t.code}{random.randint(1, 5):02d}", "finding": "See remarks", "referred_to": random.choice(["GIS unit", "IT support", "DQM"]), "action_taken": "Followed up", "resolution_status": random.choice(["OPEN", "IN_PROGRESS", "RESOLVED", "RESOLVED"])}
                for t in random.sample(teams, k=min(len(teams), random.randint(0, 3)))
            ]
            received = random.randint(10, 40)
            status = ReportStatus.RECEIVED if back >= 2 else ReportStatus.SUBMITTED if back == 1 or random.random() < 0.6 else ReportStatus.DRAFT
            at = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=18)
            db.add(
                DqmDailyReport(
                    district_id=d.id, report_date=day, period=ReportPeriod.ENUMERATION, day_number=11 - back, status=status,
                    teams_reviewed=reviewed, teams_certified=certified, executive_summary=f"Day {11 - back} in {d.name}: {len(errors)} discrepancy cases, {len(issues)} system issues.",
                    reinterviews_received=received, reinterviews_received_pending=random.randint(0, 5), reinterviews_certified=received - random.randint(0, 8), reinterviews_certified_pending=random.randint(0, 3),
                    error_profile=json.dumps(errors), system_issues=json.dumps(issues),
                    lessons=json.dumps([{"quality_area": random.choice(["GPS", "REINTERVIEW", "CAPI"]), "lesson": "Retrain on the spot", "risk": "Delays", "control": "Supervisor sit-ins"}] if random.random() < 0.5 else []),
                    sa_performance=json.dumps([{"sa": t.code, "assessment": random.choice(["On track", "Slightly behind", "Ahead"])} for t in teams[:3]]),
                    prepared_by=user.id, prepared_name=user.full_name, submitted_at=at if status != ReportStatus.DRAFT else None,
                    received_by=national.id if status == ReportStatus.RECEIVED and national else None, received_name=national.full_name if status == ReportStatus.RECEIVED and national else None,
                    received_at=at + timedelta(hours=2) if status == ReportStatus.RECEIVED else None, created_by=user.id,
                )
            )
            created += 1
    db.commit()
    print(f"Seeded {created} daily reports for {len(districts)} districts. District logins: " + ", ".join(f"dqm.{slug(d.name)}" for d in districts) + " (Password123)")


if __name__ == "__main__":
    main()
