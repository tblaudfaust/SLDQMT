"""Facilitator assessment: trainings with the chapters per day, the daily trainer ratings M&E monitors send
from the halls, and the summary by district, hall, day, trainer and monitor, with its export."""

from __future__ import annotations

import hashlib
import json
import secrets
from collections import defaultdict
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import agenda_import
from app.core import me_fac_form as form
from app.core.config import settings
from app.models import MeFacAgendaItem, MeFacAssessment, MeFacRound, User
from app.schemas.me_daily import AgendaTemplate
from app.schemas.me_fac import (
    AgendaItemIn,
    AgendaItemOut,
    AssessmentIn,
    AssessmentOut,
    CountRow,
    CriterionRow,
    GroupRow,
    PublicSubmitIn,
    PublicSubmitOut,
    RoundIn,
    RoundOut,
    RoundUpdate,
    SectionRating,
    Summary,
    TopicRow,
)
from app.services import me_daily_service, report_service

A = MeFacAssessment


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _mean(values: list[float | int | None], digits: int = 2) -> float | None:
    xs = [v for v in values if v is not None]
    return round(sum(xs) / len(xs), digits) if xs else None


def _live(round_id: int):
    return select(A).where(A.round_id == round_id, A.deleted.is_(False))


def _key(s: str | None) -> str:
    return " ".join((s or "").split()).lower()


# ---- rounds and agenda ---------------------------------------------------------------------------


def agenda_out(r: MeFacRound) -> list[AgendaItemOut]:
    return [AgendaItemOut(id=a.id, day=a.day, position=a.position, topic=a.topic, details=a.details, rated=a.rated is not False) for a in r.agenda]


def agenda_templates() -> list[AgendaTemplate]:
    """The bundled agendas, reduced to the chapters a trainer is rated on (recaps, quizzes and briefings left out)."""
    out = []
    for t in me_daily_service.agenda_templates():
        items = [i for i in t.items if form.is_rateable(i.topic)]
        out.append(AgendaTemplate(key=t.key, title=t.title, phase=t.phase, source=t.source, days=len({i.day for i in items}), day_titles=t.day_titles, items=items))
    return out


def agenda_template(key: str) -> AgendaTemplate:
    for t in agenda_templates():
        if t.key == key:
            return t
    raise HTTPException(404, f"No agenda template called {key}")


def parse_agenda_file(filename: str, data: bytes) -> dict:
    try:
        parsed = agenda_import.parse_file(filename, data)
    except Exception as e:
        raise HTTPException(400, f"Could not read {filename}: {e}") from e
    items = [AgendaItemIn(day=r.day, topic=r.topic, details=" / ".join(d for d in r.details if d) or None) for r in parsed.rows if form.is_rateable(r.topic)]
    if not items:
        raise HTTPException(400, "No chapter or session found: the file needs DAY headings and rows with a time and an activity, or the columns day, topic, details")
    return {"items": items, "days": len({i.day for i in items}), "day_titles": {str(k): v for k, v in parsed.day_titles.items()}, "warnings": parsed.warnings}


def to_out(db: Session, r: MeFacRound) -> RoundOut:
    out = RoundOut.model_validate(r)
    base = settings.ME_PUBLIC_BASE_URL.rstrip("/")
    out.share_url = f"{base}/assess/{r.token}" if base else None
    out.agenda_items = len(r.agenda)
    out.agenda_days = len({a.day for a in r.agenda})
    rows = db.execute(_live(r.id)).scalars().all()
    out.assessments = len(rows)
    out.trainers = len({_key(x.trainer_name) for x in rows})
    out.halls = len({(_key(x.district), _key(x.hall)) for x in rows})
    out.districts = len({_key(x.district) for x in rows})
    out.days = len({x.training_day for x in rows})
    out.last_date = max((x.assessment_date for x in rows), default=None)
    out.mean_pct = _mean([x.score_pct for x in rows], 1)
    out.needs_improvement = sum(1 for x in rows if x.band == "NEEDS_IMPROVEMENT")
    return out


def list_rounds(db: Session) -> list[RoundOut]:
    rows = db.execute(select(MeFacRound).order_by(MeFacRound.created_at.desc())).scalars().all()
    return [to_out(db, r) for r in rows]


def get_round(db: Session, round_id: int) -> MeFacRound:
    r = db.get(MeFacRound, round_id)
    if r is None:
        raise HTTPException(404, "Facilitator assessment not found")
    return r


def by_token(db: Session, token: str) -> MeFacRound:
    r = db.execute(select(MeFacRound).where(MeFacRound.token == token)).scalars().first()
    if r is None:
        raise HTTPException(404, "This assessment link is not valid")
    return r


def create_round(db: Session, user: User, body: RoundIn) -> MeFacRound:
    if body.period_start and body.period_end and body.period_end < body.period_start:
        raise HTTPException(400, "The period ends before it starts")
    dup = db.execute(select(MeFacRound).where(func.lower(MeFacRound.title) == body.title.strip().lower())).scalars().first()
    if dup:
        raise HTTPException(409, f"A facilitator assessment called '{dup.title}' already exists (created {dup.created_at:%d %b %Y}). Give each training a distinct title, or reopen the existing one.")
    r = MeFacRound(title=body.title.strip(), phase=body.phase, period_start=body.period_start, period_end=body.period_end,
                   description=(body.description or "").strip() or None, token=secrets.token_urlsafe(18), status="OPEN", created_by=user.id)
    db.add(r)
    db.flush()
    if body.agenda_template:
        t = agenda_template(body.agenda_template)
        set_agenda(db, r, [AgendaItemIn(day=i.day, topic=i.topic, details=i.details) for i in t.items])
    return r


def update_round(db: Session, r: MeFacRound, body: RoundUpdate) -> MeFacRound:
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(r, k, v.strip() if isinstance(v, str) and k in ("title", "description") else v)
    if r.period_start and r.period_end and r.period_end < r.period_start:
        raise HTTPException(400, "The period ends before it starts")
    db.flush()
    return r


def delete_round(db: Session, r: MeFacRound) -> None:
    if db.execute(select(func.count()).select_from(_live(r.id).subquery())).scalar_one():
        raise HTTPException(409, "This facilitator assessment has ratings; close it instead of deleting it")
    db.delete(r)
    db.flush()


def set_agenda(db: Session, r: MeFacRound, items: list[AgendaItemIn]) -> MeFacRound:
    """Replace the whole list of chapters per day (the editor sends every row)."""
    for old in list(r.agenda):
        db.delete(old)
    db.flush()
    positions: dict[int, int] = defaultdict(int)
    for a in items:
        positions[a.day] += 1
        db.add(MeFacAgendaItem(round_id=r.id, day=a.day, position=positions[a.day], topic=a.topic.strip(), details=(a.details or "").strip() or None, rated=None if a.rated else False))
    db.flush()
    db.refresh(r)
    return r


# ---- assessments ---------------------------------------------------------------------------------


def _sections(body: AssessmentIn) -> list[dict]:
    out, seen = [], set()
    for s in body.sections:
        topic = " ".join(s.topic.split())
        if not topic or topic.lower() in seen:
            continue
        seen.add(topic.lower())
        out.append({"topic": topic, "rating": s.rating})
    return out


def _apply(x: A, body: AssessmentIn) -> None:
    if body.assessment_date > date.today():
        raise HTTPException(400, "The assessment date cannot be in the future")
    sections = _sections(body)
    section_a = {"technical": body.s_technical, "clarity": body.s_clarity, "practical": body.s_practical, "participation": body.s_participation, "time": body.s_time}
    a_total, b_total, b_max, pct, band = form.score(section_a, sections)
    x.assessment_date = body.assessment_date
    x.training_day = body.training_day
    x.district = (body.district or "").strip() or None
    x.hall = " ".join(body.hall.split())
    x.monitor_name = " ".join(body.monitor_name.split())
    x.trainer_name = " ".join(body.trainer_name.split())
    x.s_technical, x.s_clarity, x.s_practical, x.s_participation, x.s_time = body.s_technical, body.s_clarity, body.s_practical, body.s_participation, body.s_time
    x.section_a_total = a_total
    x.sections = json.dumps(sections)
    x.section_b_total, x.section_b_max, x.score_pct, x.band = b_total, b_max, pct, band
    x.strengths = (body.strengths or "").strip() or None
    x.improvements = (body.improvements or "").strip() or None
    x.comments = (body.comments or "").strip() or None


def _duplicate(db: Session, r: MeFacRound, body: AssessmentIn, exclude_id: int | None) -> A | None:
    """The same monitor rating the same trainer in the same hall on the same day: one rating, corrected if needed."""
    rows = db.execute(_live(r.id).where(A.assessment_date == body.assessment_date)).scalars().all()
    for x in rows:
        if x.id != exclude_id and _key(x.trainer_name) == _key(body.trainer_name) and _key(x.hall) == _key(body.hall) and _key(x.monitor_name) == _key(body.monitor_name) and _key(x.district) == _key(body.district):
            return x
    return None


def public_submit(db: Session, r: MeFacRound, body: PublicSubmitIn) -> PublicSubmitOut:
    if r.status != "OPEN":
        raise HTTPException(409, "This facilitator assessment is closed")
    if body.assessment_id is not None:
        x = db.get(A, body.assessment_id)
        if x is None or x.round_id != r.id or x.deleted:
            raise HTTPException(404, "Rating not found")
        if not body.edit_token or x.edit_token_hash != _hash(body.edit_token):
            raise HTTPException(403, "This rating cannot be corrected from this device")
        token = body.edit_token
    else:
        x = A(round_id=r.id, submitted_at=_now())
        token = secrets.token_urlsafe(18)
        x.edit_token_hash = _hash(token)
    dup = _duplicate(db, r, body, x.id)
    if dup:
        raise HTTPException(409, f"{dup.trainer_name} was already rated by {dup.monitor_name} in {dup.hall} on {dup.assessment_date:%d %b}. Correct that rating from My sent ratings instead of sending a second one.")
    _apply(x, body)
    db.add(x)
    db.flush()
    return PublicSubmitOut(assessment_id=x.id, edit_token=token, submitted_at=x.submitted_at, section_a_total=x.section_a_total, score_pct=x.score_pct, band=x.band, band_label=form.BAND_LABEL[x.band])


def get_assessment(db: Session, round_id: int, assessment_id: int) -> A:
    x = db.get(A, assessment_id)
    if x is None or x.round_id != round_id or x.deleted:
        raise HTTPException(404, "Rating not found")
    return x


def edit_assessment(db: Session, user: User, x: A, body: AssessmentIn) -> A:
    dup = _duplicate(db, x.round, body, x.id)
    if dup:
        raise HTTPException(409, f"Another rating of {dup.trainer_name} by {dup.monitor_name} in {dup.hall} exists for that day")
    _apply(x, body)
    x.edited_by = user.id
    db.flush()
    return x


def delete_assessment(db: Session, x: A) -> None:
    x.deleted = True
    db.flush()


def editors(db: Session, rows: list[A]) -> dict[int, str]:
    ids = {x.edited_by for x in rows if x.edited_by}
    if not ids:
        return {}
    return {u.id: u.full_name for u in db.execute(select(User).where(User.id.in_(ids))).scalars()}


def to_assessment_out(x: A, editors_map: dict[int, str] | None = None) -> AssessmentOut:
    return AssessmentOut(
        id=x.id, round_id=x.round_id, assessment_date=x.assessment_date, training_day=x.training_day, district=x.district, hall=x.hall, monitor_name=x.monitor_name, trainer_name=x.trainer_name,
        s_technical=x.s_technical, s_clarity=x.s_clarity, s_practical=x.s_practical, s_participation=x.s_participation, s_time=x.s_time, section_a_total=x.section_a_total,
        section_a_band=form.band_for_total(x.section_a_total), sections=[SectionRating(**s) for s in json.loads(x.sections)], section_b_total=x.section_b_total, section_b_max=x.section_b_max,
        score_pct=x.score_pct, band=x.band, band_label=form.BAND_LABEL[x.band], strengths=x.strengths, improvements=x.improvements, comments=x.comments, submitted_at=x.submitted_at,
        edited_by_name=(editors_map or {}).get(x.edited_by or 0), lowest=min(x.s_technical, x.s_clarity, x.s_practical, x.s_participation, x.s_time),
    )


def list_assessments(db: Session, round_id: int, district: str | None = None, hall: str | None = None, trainer: str | None = None, monitor: str | None = None,
                     training_day: int | None = None, date_from: date | None = None, date_to: date | None = None) -> list[A]:
    q = _live(round_id)
    if district:
        q = q.where(func.lower(A.district) == district.lower()) if district != "HQ" else q.where(A.district.is_(None))
    if hall:
        q = q.where(func.lower(A.hall) == hall.lower())
    if trainer:
        q = q.where(func.lower(A.trainer_name) == trainer.lower())
    if monitor:
        q = q.where(func.lower(A.monitor_name) == monitor.lower())
    if training_day:
        q = q.where(A.training_day == training_day)
    if date_from:
        q = q.where(A.assessment_date >= date_from)
    if date_to:
        q = q.where(A.assessment_date <= date_to)
    return db.execute(q.order_by(A.assessment_date.desc(), A.submitted_at.desc())).scalars().all()


# ---- summary -------------------------------------------------------------------------------------

CRIT_ATTR = {"technical": "s_technical", "clarity": "s_clarity", "practical": "s_practical", "participation": "s_participation", "time": "s_time"}
CRIT_LABEL = {k: lb for k, lb, _ in form.CRITERIA}


def _group(rows: list[A], key, label, extra=None) -> list[GroupRow]:
    buckets: dict[str, list[A]] = defaultdict(list)
    labels: dict[str, str] = {}
    for x in rows:
        k = key(x)
        buckets[k].append(x)
        labels.setdefault(k, label(x))
    out = []
    for k, xs in buckets.items():
        crit = {c: _mean([getattr(x, attr) for x in xs]) for c, attr in CRIT_ATTR.items()}
        worst = min((v, c) for c, v in crit.items() if v is not None)[1] if any(v is not None for v in crit.values()) else None
        pct = _mean([x.score_pct for x in xs], 1)
        g = GroupRow(key=k, label=labels[k], assessments=len(xs), trainers=len({_key(x.trainer_name) for x in xs}), halls=len({(_key(x.district), _key(x.hall)) for x in xs}),
                     monitors=len({_key(x.monitor_name) for x in xs}), mean_a_total=_mean([x.section_a_total for x in xs], 1), mean_pct=pct, band=form.band_for_pct(pct),
                     band_label=form.BAND_LABEL.get(form.band_for_pct(pct) or "", None), criteria=crit, bands={b: sum(1 for x in xs if x.band == b) for b, *_ in form.BANDS},
                     lowest_criterion=CRIT_LABEL.get(worst or "", None), low_scores=sum(1 for x in xs if min(x.s_technical, x.s_clarity, x.s_practical, x.s_participation, x.s_time) <= 2))
        if extra:
            extra(g, xs[0])
        out.append(g)
    return out


def summary(db: Session, r: MeFacRound, **filters) -> Summary:
    rows = list_assessments(db, r.id, **filters)
    n = len(rows)
    criteria = []
    for c, attr in CRIT_ATTR.items():
        vals = [getattr(x, attr) for x in rows]
        criteria.append(CriterionRow(key=c, label=CRIT_LABEL[c], mean=_mean(vals), distribution=[CountRow(code=str(v), label=lb, count=vals.count(v), pct=round(100.0 * vals.count(v) / n, 1) if n else None) for v, lb in form.SCALE]))
    band_counts = [CountRow(code=b, label=lb, count=sum(1 for x in rows if x.band == b), pct=round(100.0 * sum(1 for x in rows if x.band == b) / n, 1) if n else None) for b, lb, _, _ in form.BANDS]
    district_of = lambda x: x.district or "National / HQ"  # noqa: E731

    def with_place(g: GroupRow, x: A):
        g.district = district_of(x)
        g.hall = x.hall

    by_district = sorted(_group(rows, lambda x: _key(x.district) or "HQ", district_of), key=lambda g: g.label)
    by_hall = sorted(_group(rows, lambda x: f"{_key(x.district) or 'HQ'}|{_key(x.hall)}", lambda x: f"{district_of(x)} · {x.hall}", with_place), key=lambda g: g.label)
    by_day = sorted(_group(rows, lambda x: str(x.training_day), lambda x: f"Day {x.training_day}"), key=lambda g: int(g.key))
    by_trainer = sorted(_group(rows, lambda x: _key(x.trainer_name), lambda x: x.trainer_name, with_place), key=lambda g: (-(g.mean_pct or 0), g.label))
    by_monitor = sorted(_group(rows, lambda x: _key(x.monitor_name), lambda x: x.monitor_name), key=lambda g: g.label)
    topic_vals: dict[tuple[int, str], list[int]] = defaultdict(list)
    for x in rows:
        for s in json.loads(x.sections):
            if s.get("rating") is not None:
                topic_vals[(x.training_day, s["topic"])].append(int(s["rating"]))
    topics = [TopicRow(day=d, topic=t, ratings=len(v), mean=_mean(v)) for (d, t), v in sorted(topic_vals.items())]
    attention = sorted([g for g in by_trainer if g.band in ("FAIR", "NEEDS_IMPROVEMENT") or g.low_scores], key=lambda g: (g.mean_pct or 0))
    ed = editors(db, rows[:30])
    return Summary(
        round=to_out(db, r), assessments=n, trainers=len({_key(x.trainer_name) for x in rows}), halls=len({(_key(x.district), _key(x.hall)) for x in rows}), districts=len({_key(x.district) for x in rows}),
        monitors=len({_key(x.monitor_name) for x in rows}), days=len({x.training_day for x in rows}), mean_a_total=_mean([x.section_a_total for x in rows], 1), mean_pct=_mean([x.score_pct for x in rows], 1),
        band_counts=band_counts, criteria=criteria, low_scores=sum(1 for x in rows if min(x.s_technical, x.s_clarity, x.s_practical, x.s_participation, x.s_time) <= 2),
        by_district=by_district, by_hall=by_hall, by_day=by_day, by_trainer=by_trainer, by_monitor=by_monitor, topics=topics, needs_attention=attention,
        latest=[to_assessment_out(x, ed) for x in rows[:30]],
    )


def export(db: Session, r: MeFacRound, **filters) -> report_service.Report:
    d = summary(db, r, **filters)
    rows = list_assessments(db, r.id, **filters)
    ed = editors(db, rows)
    outs = [to_assessment_out(x, ed) for x in rows]
    crit_headers = [CRIT_LABEL[c] for c in CRIT_ATTR]

    def g_rows(groups: list[GroupRow]):
        return [[g.label, g.assessments, g.trainers, g.mean_a_total, g.mean_pct, g.band_label or "", *[g.criteria.get(c) for c in CRIT_ATTR], g.lowest_criterion or "", g.low_scores] for g in groups]

    g_headers = ["Group", "Ratings", "Trainers", "Mean section A (of 20)", "Mean score %", "Band", *crit_headers, "Lowest criterion", "Ratings with a 1 or 2"]
    reg = [[x.assessment_date, x.training_day, x.district or "National / HQ", x.hall, x.trainer_name, x.monitor_name, x.s_technical, x.s_clarity, x.s_practical, x.s_participation, x.s_time, x.section_a_total,
            form.BAND_LABEL[x.section_a_band], x.section_b_total, x.section_b_max, x.score_pct, x.band_label, "; ".join(f"{s.topic}: {s.rating}" for s in x.sections if s.rating is not None), x.strengths or "", x.improvements or "", x.comments or "", x.submitted_at] for x in outs]
    summary_rows = [["Training", r.title], ["Ratings", d.assessments], ["Trainers", d.trainers], ["Halls", d.halls], ["Districts", d.districts], ["Monitors", d.monitors], ["Training days", d.days],
                    ["Mean section A (of 20)", d.mean_a_total], ["Mean score %", d.mean_pct], ["Ratings with a 1 or 2", d.low_scores], *[[f"Band: {c.label}", c.count] for c in d.band_counts], *[[f"Criterion: {c.label}", c.mean] for c in d.criteria]]
    fl = {k: v for k, v in filters.items() if v}
    return report_service.Report(
        kind="facilitator-assessment", title=f"Facilitator assessment · {r.title}", generated_at=_now(), filters="; ".join(f"{k}={v}" for k, v in fl.items()) or "none",
        sheets=[
            report_service.Sheet("Summary", ["Measure", "Value"], summary_rows),
            report_service.Sheet("By district", g_headers, g_rows(d.by_district)),
            report_service.Sheet("By hall", g_headers, g_rows(d.by_hall)),
            report_service.Sheet("By trainer", g_headers, g_rows(d.by_trainer), landscape=True),
            report_service.Sheet("By day", g_headers, g_rows(d.by_day)),
            report_service.Sheet("By monitor", g_headers, g_rows(d.by_monitor)),
            report_service.Sheet("Chapters", ["Day", "Chapter / section", "Ratings", "Mean (1-4)"], [[t.day, t.topic, t.ratings, t.mean] for t in d.topics]),
            report_service.Sheet("Ratings", ["Date", "Day", "District", "Hall", "Trainer", "Monitor", *crit_headers, "Section A (of 20)", "Section A band", "Section B", "Section B max", "Score %", "Band", "Sections rated", "Strengths", "To improve", "Comments", "Sent"], reg, landscape=True),
        ],
    )
