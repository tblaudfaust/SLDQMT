"""Daily Facilitator's Report: public submission with corrections from the same device, one report per hall per
day, the summary by venue, hall and day, and the export."""

from __future__ import annotations

import hashlib
import json
import secrets
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import me_facrep_form as form
from app.core.config import settings
from app.models import MeFacReport, MeFacRound, User
from app.schemas.me_facrep import CountRow, CriterionRow, GroupRow, PublicRound, PublicSubmitIn, PublicSubmitOut, ReportIn, ReportOut, RoundRow, Summary
from app.services import me_fac_service, report_service

R = MeFacReport


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _key(s: str | None) -> str:
    return " ".join((s or "").split()).lower()


def _mean(values, digits: int = 2) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return round(sum(vals) / len(vals), digits) if vals else None


def _pct(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 1) if d else None


def _live(round_id: int):
    return select(R).where(R.round_id == round_id, R.deleted.is_(False))


def report_url(r: MeFacRound) -> str | None:
    base = settings.ME_PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/report/{r.token}" if base else None


# ---- rounds (the trainings of the facilitator assessment) ---------------------------------------------


def round_row(db: Session, r: MeFacRound) -> RoundRow:
    rows = db.execute(_live(r.id)).scalars().all()
    reg, pres = sum(x.registered for x in rows), sum(x.present for x in rows)
    return RoundRow(
        round=me_fac_service.to_out(db, r), reports=len(rows), halls=len({(_key(x.venue), _key(x.hall)) for x in rows}), venues=len({_key(x.venue) for x in rows}),
        days=len({x.training_day for x in rows}), last_date=max((x.report_date for x in rows), default=None), mean_rating=_mean([x.mean_rating for x in rows]),
        attendance_pct=_pct(pres, reg), attention=sum(1 for x in rows if form.attention_reasons(x)), report_url=report_url(r),
    )


def list_rounds(db: Session) -> list[RoundRow]:
    rows = db.execute(select(MeFacRound).order_by(MeFacRound.created_at.desc())).scalars().all()
    return [round_row(db, r) for r in rows]


def public_round(db: Session, token: str) -> PublicRound:
    r = me_fac_service.by_token(db, token)
    return PublicRound(title=r.title, phase=r.phase, period_start=r.period_start, period_end=r.period_end, description=r.description, status=r.status, agenda=me_fac_service.agenda_out(r), form=form.public_spec())


# ---- reports ---------------------------------------------------------------------------------------------


def _apply(x: R, body: ReportIn) -> None:
    for key in ("report_date", "training_day", "venue", "hall", "lead_facilitator", "other_facilitators", "email", "phone", "registered", "present", "delivered", "minutes_lost", "missed_reason",
                "r_knowledge", "r_engagement", "r_illustrations", "r_connectivity", "r_coordination", "e_internet", "e_internet_details", "e_power", "e_power_details", "e_devices", "e_devices_details",
                "e_food", "e_food_details", "went_right", "repeat_share", "went_wrong", "difficult_notes", "recommendations", "gaps", "actor_other", "comments"):
        v = getattr(body, key)
        setattr(x, key, (v.strip() or None) if isinstance(v, str) and key not in ("venue", "hall", "lead_facilitator", "delivered", "went_right", "went_wrong", "recommendations", "gaps") else v)
    x.venue, x.hall, x.lead_facilitator = body.venue.strip(), body.hall.strip(), body.lead_facilitator.strip()
    x.missed_sessions = json.dumps([s.strip() for s in body.missed_sessions if s.strip()][:40])
    x.difficult_topics = json.dumps([s.strip() for s in body.difficult_topics if s.strip()][:40])
    x.actors = json.dumps([a for a in body.actors if a in form.ACTOR_KEYS])
    if body.delivered == "FULL":
        x.missed_sessions, x.minutes_lost, x.missed_reason = "[]", None, None
    x.mean_rating = form.mean_rating({k: getattr(body, f"r_{k}") for k in form.RATING_KEYS})


def _duplicate(db: Session, r: MeFacRound, body: ReportIn, exclude_id: int | None) -> R | None:
    """One report per hall per day."""
    for x in db.execute(_live(r.id).where(R.report_date == body.report_date)).scalars():
        if x.id != exclude_id and _key(x.venue) == _key(body.venue) and _key(x.hall) == _key(body.hall):
            return x
    return None


def public_submit(db: Session, r: MeFacRound, body: PublicSubmitIn) -> PublicSubmitOut:
    if r.status != "OPEN":
        raise HTTPException(409, "This training is closed; reports are no longer accepted")
    if body.report_id is not None:
        x = db.get(R, body.report_id)
        if x is None or x.round_id != r.id or x.deleted:
            raise HTTPException(404, "Report not found")
        if not body.edit_token or x.edit_token_hash != _hash(body.edit_token):
            raise HTTPException(403, "This report cannot be corrected from this device")
        token = body.edit_token
    else:
        x = R(round_id=r.id, submitted_at=_now())
        token = secrets.token_urlsafe(18)
        x.edit_token_hash = _hash(token)
    dup = _duplicate(db, r, body, x.id)
    if dup:
        raise HTTPException(409, f"A report for {dup.hall} in {dup.venue} on {dup.report_date:%d %b} was already sent by {dup.lead_facilitator}. One report per hall per day: correct it from My sent reports on the device that sent it.")
    _apply(x, body)
    db.add(x)
    db.flush()
    return PublicSubmitOut(report_id=x.id, edit_token=token, submitted_at=x.submitted_at, mean_rating=x.mean_rating, attendance_pct=_pct(x.present, x.registered))


def get_report(db: Session, round_id: int, report_id: int) -> R:
    x = db.get(R, report_id)
    if x is None or x.round_id != round_id or x.deleted:
        raise HTTPException(404, "Report not found")
    return x


def edit_report(db: Session, user: User, x: R, body: ReportIn) -> R:
    dup = _duplicate(db, x.round, body, x.id)
    if dup:
        raise HTTPException(409, f"Another report for {dup.hall} in {dup.venue} on {dup.report_date:%d %b} already exists")
    _apply(x, body)
    x.edited_by = user.id
    db.flush()
    return x


def delete_report(db: Session, x: R) -> None:
    x.deleted = True
    db.flush()


def editors(db: Session, rows: list[R]) -> dict[int, str]:
    ids = {x.edited_by for x in rows if x.edited_by}
    if not ids:
        return {}
    return {u.id: u.full_name for u in db.execute(select(User).where(User.id.in_(ids))).scalars()}


def to_out(x: R, ed: dict[int, str] | None = None) -> ReportOut:
    out = ReportOut.model_validate(x, from_attributes=True, strict=False) if False else ReportOut(
        id=x.id, round_id=x.round_id, report_date=x.report_date, training_day=x.training_day, venue=x.venue, hall=x.hall, lead_facilitator=x.lead_facilitator, other_facilitators=x.other_facilitators,
        email=x.email, phone=x.phone, registered=x.registered, present=x.present, attendance_pct=_pct(x.present, x.registered), delivered=x.delivered, delivered_label=form.DELIVERY_LABEL.get(x.delivered, x.delivered),
        missed_sessions=json.loads(x.missed_sessions or "[]"), minutes_lost=x.minutes_lost, missed_reason=x.missed_reason,
        r_knowledge=x.r_knowledge, r_engagement=x.r_engagement, r_illustrations=x.r_illustrations, r_connectivity=x.r_connectivity, r_coordination=x.r_coordination, mean_rating=x.mean_rating,
        e_internet=x.e_internet, e_internet_details=x.e_internet_details, e_power=x.e_power, e_power_details=x.e_power_details, e_devices=x.e_devices, e_devices_details=x.e_devices_details, e_food=x.e_food, e_food_details=x.e_food_details,
        went_right=x.went_right, repeat_share=x.repeat_share, went_wrong=x.went_wrong, difficult_topics=json.loads(x.difficult_topics or "[]"), difficult_notes=x.difficult_notes, recommendations=x.recommendations, gaps=x.gaps,
        actors=json.loads(x.actors or "[]"), actor_labels=[form.ACTOR_LABEL.get(a, a) for a in json.loads(x.actors or "[]")], actor_other=x.actor_other, comments=x.comments,
        submitted_at=x.submitted_at, edited_by_name=(ed or {}).get(x.edited_by or 0), reasons=form.attention_reasons(x),
    )
    return out


def list_reports(db: Session, round_id: int, venue: str | None = None, hall: str | None = None, training_day: int | None = None, date_from: date | None = None, date_to: date | None = None) -> list[R]:
    q = _live(round_id)
    if training_day:
        q = q.where(R.training_day == training_day)
    if date_from:
        q = q.where(R.report_date >= date_from)
    if date_to:
        q = q.where(R.report_date <= date_to)
    rows = db.execute(q.order_by(R.report_date.desc(), R.submitted_at.desc())).scalars().all()
    if venue:
        rows = [x for x in rows if _key(x.venue) == _key(venue)]
    if hall:
        rows = [x for x in rows if _key(x.hall) == _key(hall)]
    return rows


# ---- summary ---------------------------------------------------------------------------------------------


def _group(rows: list[R], key, label, extra=None) -> list[GroupRow]:
    buckets: dict[str, list[R]] = defaultdict(list)
    labels: dict[str, str] = {}
    for x in rows:
        k = key(x)
        buckets[k].append(x)
        labels.setdefault(k, label(x))
    out = []
    for k, xs in buckets.items():
        reg, pres = sum(x.registered for x in xs), sum(x.present for x in xs)
        g = GroupRow(
            key=k, label=labels[k], reports=len(xs), halls=len({(_key(x.venue), _key(x.hall)) for x in xs}), days=len({x.training_day for x in xs}), registered=reg, present=pres,
            attendance_pct=_pct(pres, reg), mean_rating=_mean([x.mean_rating for x in xs]), ratings={c: _mean([getattr(x, f"r_{c}") for x in xs]) for c in form.RATING_KEYS},
            delivered_full_pct=_pct(sum(1 for x in xs if x.delivered == "FULL"), len(xs)), minutes_lost=sum(x.minutes_lost or 0 for x in xs),
            internet=_mean([x.e_internet for x in xs]), power=_mean([x.e_power for x in xs]),
            low_ratings=sum(1 for x in xs if any(getattr(x, f"r_{c}") <= 2 for c in form.RATING_KEYS)), attention=sum(1 for x in xs if form.attention_reasons(x)),
        )
        if extra:
            extra(g, xs[0])
        out.append(g)
    return out


def _counts(items: list[str], labels: dict[str, str] | None, n: int) -> list[CountRow]:
    c = Counter(items)
    return [CountRow(code=k, label=(labels or {}).get(k, k), count=v, pct=_pct(v, n)) for k, v in c.most_common()]


def summary(db: Session, r: MeFacRound, **filters) -> Summary:
    rows = list_reports(db, r.id, **filters)
    ed = editors(db, rows)
    n = len(rows)
    reg, pres = sum(x.registered for x in rows), sum(x.present for x in rows)
    criteria = []
    for c in form.RATING_KEYS:
        vals = [getattr(x, f"r_{c}") for x in rows]
        criteria.append(CriterionRow(key=c, label=form.RATING_LABEL[c], mean=_mean(vals), distribution=[CountRow(code=str(v), label=lb, count=vals.count(v), pct=_pct(vals.count(v), n)) for v, lb in form.SCALE]))

    def set_venue(g: GroupRow, x: R):
        g.venue, g.hall = x.venue, x.hall

    attention = [to_out(x, ed) for x in rows if form.attention_reasons(x)]
    return Summary(
        round=me_fac_service.to_out(db, r), report_url=report_url(r), reports=n, halls=len({(_key(x.venue), _key(x.hall)) for x in rows}), venues=len({_key(x.venue) for x in rows}),
        days=len({x.training_day for x in rows}), facilitators=len({_key(x.lead_facilitator) for x in rows}), registered=reg, present=pres, attendance_pct=_pct(pres, reg),
        mean_rating=_mean([x.mean_rating for x in rows]), delivered=[CountRow(code=v, label=lb, count=sum(1 for x in rows if x.delivered == v), pct=_pct(sum(1 for x in rows if x.delivered == v), n)) for v, lb in form.DELIVERY],
        minutes_lost=sum(x.minutes_lost or 0 for x in rows), internet=_mean([x.e_internet for x in rows]), power=_mean([x.e_power for x in rows]), criteria=criteria,
        low_ratings=sum(1 for x in rows if any(getattr(x, f"r_{c}") <= 2 for c in form.RATING_KEYS)), attention=len(attention),
        by_venue=sorted(_group(rows, lambda x: _key(x.venue), lambda x: x.venue), key=lambda g: g.label),
        by_hall=sorted(_group(rows, lambda x: f"{_key(x.venue)}|{_key(x.hall)}", lambda x: f"{x.venue} · {x.hall}", set_venue), key=lambda g: g.label),
        by_day=sorted(_group(rows, lambda x: str(x.training_day), lambda x: f"Day {x.training_day}"), key=lambda g: int(g.key)),
        actors=_counts([a for x in rows for a in json.loads(x.actors or "[]")], form.ACTOR_LABEL, n),
        difficult_topics=_counts([t for x in rows for t in json.loads(x.difficult_topics or "[]")], None, n)[:25],
        missed_sessions=_counts([t for x in rows for t in json.loads(x.missed_sessions or "[]")], None, n)[:25],
        needs_attention=attention[:50], latest=[to_out(x, ed) for x in rows[:20]],
    )


def export(db: Session, r: MeFacRound, **filters) -> report_service.Report:
    d = summary(db, r, **filters)
    rows = list_reports(db, r.id, **filters)
    outs = [to_out(x, editors(db, rows)) for x in rows]
    crit = [form.RATING_LABEL[c] for c in form.RATING_KEYS]

    def g_rows(groups: list[GroupRow]):
        return [[g.label, g.reports, g.halls, g.registered, g.present, g.attendance_pct, g.mean_rating, *[g.ratings.get(c) for c in form.RATING_KEYS], g.delivered_full_pct, g.minutes_lost, g.internet, g.power, g.low_ratings, g.attention] for g in groups]

    g_headers = ["Group", "Reports", "Halls", "Registered", "Present", "Attendance %", "Mean rating (1-5)", *crit, "Delivered fully %", "Minutes lost", "Internet (1-5)", "Power (1-5)", "Reports with a 1 or 2", "Need attention"]
    reg = [[x.report_date, x.training_day, x.venue, x.hall, x.lead_facilitator, x.other_facilitators or "", x.email or "", x.registered, x.present, x.attendance_pct, x.delivered_label, "; ".join(x.missed_sessions), x.minutes_lost, x.missed_reason or "",
            x.r_knowledge, x.r_engagement, x.r_illustrations, x.r_connectivity, x.r_coordination, x.mean_rating, x.e_internet, x.e_internet_details or "", x.e_power, x.e_power_details or "", x.e_devices or "", x.e_devices_details or "",
            x.e_food or "", x.e_food_details or "", x.went_right, x.repeat_share or "", x.went_wrong, "; ".join(x.difficult_topics), x.difficult_notes or "", x.recommendations, x.gaps, "; ".join(x.actor_labels), x.actor_other or "", x.comments or "",
            x.submitted_at, "; ".join(x.reasons)] for x in outs]
    summary_rows = [["Training", r.title], ["Reports", d.reports], ["Halls", d.halls], ["Venues", d.venues], ["Training days", d.days], ["Lead facilitators", d.facilitators], ["Participants registered (sum of reports)", d.registered],
                    ["Participants present (sum of reports)", d.present], ["Attendance %", d.attendance_pct], ["Mean class rating (1-5)", d.mean_rating], *[[f"Delivered: {c.label}", c.count] for c in d.delivered], ["Minutes lost", d.minutes_lost],
                    ["Internet connectivity (1-5)", d.internet], ["Power supply (1-5)", d.power], *[[f"Rating: {c.label}", c.mean] for c in d.criteria], ["Reports with a 1 or 2", d.low_ratings], ["Reports needing attention", d.attention]]
    fl = {k: v for k, v in filters.items() if v}
    return report_service.Report(
        kind="facilitator-report", title=f"Daily Facilitator's Report · {r.title}", generated_at=_now(), filters="; ".join(f"{k}={v}" for k, v in fl.items()) or "none",
        sheets=[
            report_service.Sheet("Summary", ["Measure", "Value"], summary_rows),
            report_service.Sheet("By venue", g_headers, g_rows(d.by_venue), landscape=True),
            report_service.Sheet("By hall", g_headers, g_rows(d.by_hall), landscape=True),
            report_service.Sheet("By day", g_headers, g_rows(d.by_day), landscape=True),
            report_service.Sheet("Who should act", ["Actor", "Reports", "%"], [[c.label, c.count, c.pct] for c in d.actors]),
            report_service.Sheet("Difficult topics", ["Topic", "Reports", "%"], [[c.label, c.count, c.pct] for c in d.difficult_topics]),
            report_service.Sheet("Sessions affected", ["Session", "Reports", "%"], [[c.label, c.count, c.pct] for c in d.missed_sessions]),
            report_service.Sheet("Reports", ["Date", "Day", "Venue", "Hall", "Lead facilitator", "Other facilitators", "Email", "Registered", "Present", "Attendance %", "Delivered", "Sessions affected", "Minutes lost", "Why",
                                             *crit, "Mean rating", "Internet", "Internet details", "Power", "Power details", "Device shortages", "Device details", "Food & beverages", "Food details",
                                             "What worked well", "To repeat / share", "What did not work", "Difficult topics", "Difficult notes", "Recommended actions", "Gaps / errors", "Who should act", "Other actor", "Comments", "Sent", "Needs attention"], reg, landscape=True),
        ],
    )


# ---- the ToT training shipped with the server ----------------------------------------------------

TOT_MARKER = "me_facrep_tot_round"
TOT_TITLE = "Training of Trainers (in-person), 2026"


def ensure_tot_round(db: Session) -> MeFacRound | None:
    """Start-up hook: the first time the server runs with this module, create the Training of Trainers entry
    with the 2026 agenda so that the Daily Facilitator's Report link and QR code exist from day one (once only:
    a training the M&E team renames, closes or deletes afterwards is not re-created)."""
    from app.models import Setting

    if db.get(Setting, TOT_MARKER) is not None:
        return None
    r = db.execute(select(MeFacRound).where(MeFacRound.phase == "TOT")).scalars().first()
    if r is None:
        from app.schemas.me_fac import AgendaItemIn

        r = MeFacRound(title=TOT_TITLE, phase="TOT", description="Lead Facilitators: send one Daily Facilitator's Report per hall at the end of each training day.",
                       token=secrets.token_urlsafe(18), status="OPEN")
        db.add(r)
        db.flush()
        try:
            t = me_fac_service.agenda_template("TRAINING_2026")
            me_fac_service.set_agenda(db, r, [AgendaItemIn(day=i.day, topic=i.topic, details=i.details) for i in t.items])
        except HTTPException:  # the bundled agenda is missing: the training still exists, chapters are typed later
            pass
    db.add(Setting(key=TOT_MARKER, value=date.today().isoformat()))
    db.commit()
    return r
