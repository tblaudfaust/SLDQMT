"""Demonstration data for the M&E Field Tool: the same set of KPI reports in every district, submitted by
"Demo User". Idempotent: a version marker in the settings table records what was loaded; a new version
replaces the previous demo reports (and nothing else). Run inside the server container:

    python -m app.services.me_kpi_demo            # load (or refresh) the demo data
    python -m app.services.me_kpi_demo --remove   # delete the demo reports
"""

from __future__ import annotations

import random
import secrets
import sys
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import District, EnumerationArea, MeKpiReport, Setting, Supervisor, Team, User
from app.models.user import Role
from app.schemas.me_kpi import ReportIn, SyncIn
from app.services import me_kpi_service as svc

VERSION = "1"
MARKER = "me_kpi_demo_version"
DEMO_USERNAME = "demo.me"
DEMO_NAME = "Demo User"
DEVICE = "demo-seed"  # every demo report carries this device tag
SAS_PER_DISTRICT = 3

# approximate centre of each district, for the GPS position of the in-person visits
CENTRES = {"11": (8.28, -10.57), "12": (7.88, -11.19), "13": (8.64, -10.97), "21": (8.88, -12.04), "22": (9.67, -11.33), "23": (9.59, -11.55), "24": (8.72, -11.95),
           "31": (9.12, -12.92), "32": (9.10, -12.40), "33": (8.77, -12.79), "41": (7.96, -11.74), "42": (7.53, -12.50), "43": (8.16, -12.43), "44": (7.36, -11.72), "51": (8.34, -13.07), "52": (8.48, -13.23)}

CHANNELS = ["radio", "meetings", "religious", "leaders", "posters", "sms", "social"]
BLOCKERS = ["connectivity", "validation", "bundle", "missing"]
ERROR_TYPES = ["missing", "coordinates", "skips", "age", "duplicate", "mislabel"]
RISKS = ["connectivity", "electricity", "device", "weather", "transport", "security", "turnover"]
STRENGTHS = ["Supervisor reviews every case before sync", "Enumerators know the EA map well", "Community leaders accompany the team", "Daily team debrief at 17:00", "Tablets charged overnight at the chief's compound"]
WEAKNESSES = ["Slow sync in the evening", "One enumerator behind on callbacks", "Map boundary unclear at the river", "Data bundle finished on day 4", "Long walking distance between localities"]
HARD = ["Riverine settlements reachable by boat only", "Mining camp outside the mapped locality", "Fishing community away during the week", "Farm hamlets 2 hours from the road"]


def _demo_user(db: Session) -> User:
    u = db.execute(select(User).where(User.username == DEMO_USERNAME)).scalars().first()
    if u is None:
        # the owner of the demo reports; it cannot sign in (inactive, random password)
        u = User(username=DEMO_USERNAME, password_hash=hash_password(secrets.token_urlsafe(24)), full_name=DEMO_NAME, role=Role.ME, active=False, must_change_password=False)
        db.add(u)
        db.flush()
    return u


def _pick(rng: random.Random, options: list[str], k: int) -> list[str]:
    return rng.sample(options, min(k, len(options)))


def _answers(rng: random.Random, phase: str, week: int | None, team_index: int) -> dict:
    """One set of answers; the same seed gives the same answers in every district."""
    practice = phase in ("MT", "TOT", "TOE")
    progress = {None: 0.75, 1: 0.42, 2: 0.78, 3: 0.95}[week if week in (1, 2, 3) else None]
    expected = 60 if practice else rng.choice([520, 610, 680, 740])
    done = int(expected * min(1.0, progress + rng.uniform(-0.08, 0.08)))
    reviewed = max(1, int(done * rng.uniform(0.3, 0.6)))
    errors = int(reviewed * rng.choice([0.01, 0.02, 0.03, 0.04, 0.06, 0.09]))
    completed = done
    synced = int(completed * rng.choice([1.0, 1.0, 0.97, 0.92, 0.84, 0.7]))
    issued = 6 if practice else rng.choice([5, 6, 7])
    working = issued - (1 if rng.random() < 0.15 else 0)
    on_schedule = rng.choices(["1", "2", "3"], weights=[72, 20, 8])[0]
    overall = rng.choices(["4", "3", "2", "1"], weights=[35, 45, 15, 5])[0]
    safety = rng.random() < 0.08
    escalate = rng.random() < 0.12 or safety
    selected = 10 if not practice else 4
    a: dict = {
        "k1_1": "1" if rng.random() < 0.85 else "2",
        "k1_2": _pick(rng, CHANNELS, rng.randint(2, 4)),
        "k1_3": "1" if rng.random() < 0.7 else "2",
        "k1_4": rng.choice(["None raised", "Some ask whether the census is linked to taxes", "Rumour that the data goes to political parties", "Questions about the enumerators' IDs"]),
        "k1_5": "1" if rng.random() < 0.8 else "2",
        "k2_1": rng.choices(["1", "2", "3", "4"], weights=[40, 45, 12, 3])[0],
        "k2_2": "1" if rng.random() < 0.9 else "2",
        "k2_3": rng.choices(["1", "2", "8"], weights=[60, 25, 15])[0],
        "k2_4": "1" if rng.random() < 0.3 else "2",
        "k2_5": "1" if rng.random() < 0.88 else "2",
        "k3_1": {"expected": expected, "done": done},
        "k3_7": "1" if rng.random() < 0.9 else "2",
        "k3_8": "1" if rng.random() < 0.8 else "2",
        "k3_9": "1" if rng.random() < 0.25 else "2",
        "k3_4": "1" if rng.random() < 0.2 else "2",
        "k3_5": "1" if rng.random() < 0.5 else "2",
        "k4_1": {"working": working, "issued": issued},
        "k4_2": "1" if rng.random() < 0.2 else "2",
        "k4_3": rng.choices(["1", "2", "8"], weights=[65, 15, 20])[0],
        "k4_4": "1" if rng.random() < 0.9 else "2",
        "k5_1": {"urban": int(done * 0.3 / max(1, (week or 1) * 5)), "rural": int(done * 0.7 / max(1, (week or 1) * 5))},
        "k5_3": rng.choice(["Heavy rain on two afternoons", "Market day reduced the households at home", "No issue", "Transport delayed the team on Monday"]),
        "k5_4": rng.choice(HARD),
        "k6_1": {"completed": completed, "synced": synced},
        "k6_2": _pick(rng, BLOCKERS, rng.randint(0, 2)) or ["none"],
        "k6_3": rng.choices(["1", "2", "3"], weights=[60, 30, 10])[0],
        "k7_1": {"reviewed": reviewed, "errors": errors},
        "k7_3": _pick(rng, ERROR_TYPES, rng.randint(1, 3)),
        "k7_4": "1" if rng.random() < 0.75 else "2",
        "k8_0": "1" if rng.random() < 0.85 else "2",
        "k8_1": {"selected": selected, "done": int(selected * rng.choice([1.0, 1.0, 0.8, 0.6]))},
        "k8_2": rng.choice([1, 1, 2, 3]),
        "k8_3": "1" if rng.random() < 0.3 else "2",
        "k8_4": rng.choices(["1", "2", "8"], weights=[70, 10, 20])[0],
        "k9_1": "1" if rng.random() < 0.8 else "2",
        "k9_2": "1" if rng.random() < 0.3 else "2",
        "k9_3": "1" if rng.random() < 0.7 else "2",
        "k9_4": "1" if rng.random() < 0.6 else "2",
        "k9_5": rng.choice([2, 3, 4, 5]),
        "k9_6": "1" if rng.random() < 0.2 else "2",
        "k10_1": rng.choices(["1", "2", "3"], weights=[70, 25, 5])[0],
        "k10_2": "1" if rng.random() < 0.85 else "2",
        "k10_3": rng.choices(["1", "2", "3", "4"], weights=[60, 25, 10, 5])[0],
        "k10_4": rng.choices(["1", "2", "3", "4"], weights=[50, 30, 12, 8])[0],
        "k10_5": rng.choice(["Network only at the chiefdom headquarters", "None", "Bundle runs out before the end of the week", "Sync fails after 18:00"]),
        "k11_1": rng.choice(STRENGTHS),
        "k11_2": rng.choice(WEAKNESSES),
        "k11_3": rng.choice(["Escalation goes through the FC by phone; works", "No feedback yet on the issues reported last week", "WhatsApp group of the district is active"]),
        "k11_5": rng.choice(["None", "A section chief asked for a courtesy visit first", "Youth asked about jobs"]),
        "k11_6": _pick(rng, RISKS, rng.randint(1, 3)),
        "b1": overall,
    }
    if a["k1_2"] and "other" in a["k1_2"]:
        a["k1_2_detail"] = "Town crier"
    if a["k1_3"] == "2":
        a["k1_3_detail"] = rng.choice(["Nomadic herders near the border", "Persons with disabilities in remote hamlets", "Language minority (Fula) households"])
    if a["k1_5"] == "1":
        a["k1_5_detail"] = rng.choice(["Toll-free line and the chief's office", "Field Coordinator's phone number on the poster"])
    if a["k2_2"] == "2":
        a["k2_2_detail"] = "They doubt the purpose and fear tax collection"
    if a["k2_4"] == "1":
        a["k2_4_detail"] = rng.choice(["Weekly market on Thursday", "Fishing season: men at sea from 5 am", "Rice harvest keeps households on the farm"])
    if a["k3_7"] == "2":
        a["k3_7_detail"] = "Three structures across the stream belong to the next EA"
    if a["k3_8"] == "2":
        a["k3_8_detail"] = "Farm hamlets to the north not yet visited"
    if a["k3_9"] == "1":
        a["k3_9_detail"] = f"{rng.randint(2, 9)} new structures added to the listing"
    if a["k3_4"] == "1":
        a["k3_4_detail"] = f"{rng.randint(1, 4)} refusals; the chief will accompany the enumerator"
    if a["k3_5"] == "1":
        a["k3_5_detail"] = f"{rng.randint(3, 15)} callbacks planned for the weekend"
    if a["k4_2"] == "1":
        a["k4_2_detail"] = "GPS drifts under the forest canopy"
    if a["k6_2"] and "other" in a["k6_2"]:
        a["k6_2_detail"] = "Tablet update pending"
    if a["k8_3"] == "1":
        a["k8_3_detail"] = f"{rng.randint(1, 3)} households: household size differed"
    if a["k9_3"] == "1":
        a["k9_3_detail"] = str(rng.randint(1, 3))
    if a["k9_4"] == "1":
        a["k9_4_detail"] = str(rng.randint(1, 2))
    if a["k9_6"] == "1":
        a["k9_6_detail"] = "Supervisor absent on Tuesday"
    if not practice:
        a["k3_6"] = "1" if rng.random() < 0.12 else "2"
        if a["k3_6"] == "1":
            a["k3_6_detail"] = "EA 3: enumerator fell sick, 2 days lost"
        a["k5_2"] = on_schedule
    if safety:
        a["k11_4"] = rng.choice(["Threats at the market against the enumerators", "Road blocked by a land dispute", "Youth group demanded payment before access"])
    if escalate:
        a["b2"] = rng.choice(["Replacement tablet · District IT · by Friday", "Police escort for EA 2 · DCO · tomorrow", "Data bundle top-up · FC · today"])
    a["b3"] = "1" if rng.random() < 0.3 else "2"
    if a["b3"] == "1":
        a["b3_detail"] = (date.today() + timedelta(days=rng.randint(2, 7))).isoformat()
    return a


def _plan(today: date) -> list[tuple[str, int | None, int]]:
    """(phase, week, days before today) of every report of one SA."""
    return [("MT", None, 28), ("TOT", None, 21), ("TOE", None, 17), ("L", 1, 13), ("L", 2, 6), ("E", 1, 2)]


def remove_demo(db: Session) -> int:
    u = db.execute(select(User).where(User.username == DEMO_USERNAME)).scalars().first()
    if u is None:
        return 0
    rows = db.execute(select(MeKpiReport).where(MeKpiReport.user_id == u.id, MeKpiReport.device == DEVICE)).scalars().all()
    for r in rows:
        db.delete(r)
    db.flush()
    return len(rows)


def seed_demo(db: Session, force: bool = False) -> dict:
    """Load the demo reports unless this version is already there. Returns counts."""
    marker = db.get(Setting, MARKER)
    if marker is not None and marker.value == VERSION and not force:
        return {"status": "already loaded", "version": VERSION, "created": 0}
    removed = remove_demo(db)
    user = _demo_user(db)
    today = date.today()
    districts = db.execute(select(District).order_by(District.code)).scalars().all()
    reports: list[ReportIn] = []
    for d in districts:
        teams = db.execute(select(Team).where(Team.district_id == d.id, Team.active.is_(True)).order_by(Team.code)).scalars().all()[:SAS_PER_DISTRICT]
        lat, lng = CENTRES.get(d.code, (8.5, -12.0))
        for i, t in enumerate(teams):
            ea = db.execute(select(EnumerationArea).where(EnumerationArea.team_id == t.id).order_by(EnumerationArea.code)).scalars().first()
            sup = db.execute(select(Supervisor).where(Supervisor.team_id == t.id)).scalars().first()
            sup_name = getattr(sup, "name", None) or f"Supervisor {t.code}"
            for phase, week, days_ago in _plan(today):
                rng = random.Random(f"{VERSION}|{i}|{phase}|{week}")  # same numbers in every district
                practice = phase in ("MT", "TOT", "TOE")
                remote = (not practice) and rng.random() < 0.15
                reports.append(ReportIn(
                    client_id=f"demo-{d.code}-{t.code}-{phase}-{week or 0}-{VERSION}"[:48], phase=phase, report_date=today - timedelta(days=days_ago + i), week=week,
                    district_id=d.id, chiefdom=t.chiefdom, team_id=None if practice else t.id, sa_code=None if practice else t.code, ea_codes=[] if practice or not ea else [ea.code],
                    practice_team=f"Hall {i + 1} · Team {'ABC'[i]}" if practice else None, respondent_name=sup_name if not practice else f"Trainee group {i + 1}",
                    respondent_role="SUPERVISOR" if not practice else "TRAINEE", collection_mode="REMOTE" if remote else "IN_PERSON",
                    eas_urban=rng.randint(1, 3), eas_rural=rng.randint(2, 5), enumerators=rng.randint(4, 7), capi_version="2.3.1",
                    lat=None if remote else round(lat + rng.uniform(-0.05, 0.05), 5), lng=None if remote else round(lng + rng.uniform(-0.05, 0.05), 5),
                    answers=_answers(rng, phase, week, i), device=DEVICE,
                ))
    out = svc.sync(db, user, SyncIn(reports=reports[:200]), can_manage=True) if reports else None
    created = out.created if out else 0
    errors = [r.message for r in out.results if r.status == "error"] if out else []
    for chunk_start in range(200, len(reports), 200):
        o = svc.sync(db, user, SyncIn(reports=reports[chunk_start:chunk_start + 200]), can_manage=True)
        created += o.created
        errors += [r.message for r in o.results if r.status == "error"]
    if marker is None:
        db.add(Setting(key=MARKER, value=VERSION))
    else:
        marker.value = VERSION
    db.flush()
    return {"status": "loaded", "version": VERSION, "districts": len(districts), "removed": removed, "created": created, "errors": errors[:5]}


def main(argv: list[str]) -> int:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        if "--remove" in argv:
            n = remove_demo(db)
            m = db.get(Setting, MARKER)
            if m is not None:
                db.delete(m)
            db.commit()
            print(f"removed {n} demo reports")
        else:
            res = seed_demo(db, force="--force" in argv)
            db.commit()
            print(res)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
