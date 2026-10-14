"""Daily Evaluation: rounds with their agenda, the Daily Facilitator Reports lead facilitators send, and
the summary (every indicator, grouped by day, class, district, facilitator, phase and topic) with its export."""

from __future__ import annotations

import hashlib
import json
import secrets
from collections import defaultdict
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import me_daily_form as form
from app.core.config import settings
from app.models import MeDailyAgendaItem, MeDailyFacilitatorReport, MeDailyRound, User
from app.schemas.me_daily import (
    AgendaItemIn,
    AgendaItemOut,
    CountRow,
    Escalation,
    GroupRow,
    LogRow,
    MaterialIssue,
    PublicSubmitIn,
    PublicSubmitOut,
    ReportIn,
    ReportOut,
    RoundIn,
    RoundOut,
    RoundUpdate,
    SessionRow,
    Summary,
    TopicRow,
)
from app.services import report_service

Report = MeDailyFacilitatorReport


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _pct(n: float, d: float) -> float | None:
    return round(100.0 * n / d, 1) if d else None


def _mean(values: list[float | int | None]) -> float | None:
    xs = [v for v in values if v is not None]
    return round(sum(xs) / len(xs), 2) if xs else None


def _live(round_id: int):
    return select(Report).where(Report.round_id == round_id, Report.deleted.is_(False))


# ---- rounds and agenda ---------------------------------------------------------------------------


def agenda_out(r: MeDailyRound) -> list[AgendaItemOut]:
    return [AgendaItemOut(id=a.id, day=a.day, position=a.position, topic=a.topic, planned_start=a.planned_start, planned_end=a.planned_end) for a in r.agenda]


def to_out(db: Session, r: MeDailyRound) -> RoundOut:
    out = RoundOut.model_validate(r)
    base = settings.ME_PUBLIC_BASE_URL.rstrip("/")
    out.share_url = f"{base}/daily/{r.token}" if base else None
    out.agenda_items = len(r.agenda)
    out.agenda_days = len({a.day for a in r.agenda})
    rows = db.execute(_live(r.id)).scalars().all()
    out.reports = len(rows)
    out.classes = len({x.class_hall.strip().lower() for x in rows})
    out.days = len({x.training_day for x in rows})
    out.last_report_date = max((x.report_date for x in rows), default=None)
    out.overall_mean = _mean([x.overall for x in rows])
    sessions = [s for x in rows for s in json.loads(x.sessions)]
    out.delivered_pct = _pct(sum(1 for s in sessions if s.get("delivered") == "Y"), len(sessions))
    out.open_escalations = sum(1 for x in rows for e in json.loads(x.escalations) if e.get("status") != "RESOLVED")
    out.low_scores = sum(1 for x in rows if min(x.q_content, x.q_engagement, x.q_time, x.q_illustrations) <= 2)
    return out


def list_rounds(db: Session) -> list[RoundOut]:
    rows = db.execute(select(MeDailyRound).order_by(MeDailyRound.created_at.desc())).scalars().all()
    return [to_out(db, r) for r in rows]


def get_round(db: Session, round_id: int) -> MeDailyRound:
    r = db.get(MeDailyRound, round_id)
    if r is None:
        raise HTTPException(404, "Daily evaluation not found")
    return r


def by_token(db: Session, token: str) -> MeDailyRound:
    r = db.execute(select(MeDailyRound).where(MeDailyRound.token == token)).scalars().first()
    if r is None:
        raise HTTPException(404, "This daily evaluation link is not valid")
    return r


def create_round(db: Session, user: User, body: RoundIn) -> MeDailyRound:
    if body.period_start and body.period_end and body.period_end < body.period_start:
        raise HTTPException(400, "The period ends before it starts")
    dup = db.execute(select(MeDailyRound).where(func.lower(MeDailyRound.title) == body.title.strip().lower())).scalars().first()
    if dup:
        raise HTTPException(409, f"A daily evaluation called '{dup.title}' already exists (created {dup.created_at:%d %b %Y}). Give each training a distinct title, or reopen the existing one.")
    r = MeDailyRound(title=body.title.strip(), phase=body.phase, period_start=body.period_start, period_end=body.period_end,
                     description=(body.description or "").strip() or None, token=secrets.token_urlsafe(18), status="OPEN", created_by=user.id)
    db.add(r)
    db.flush()
    return r


def update_round(db: Session, r: MeDailyRound, body: RoundUpdate) -> MeDailyRound:
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(r, k, v.strip() if isinstance(v, str) and k in ("title", "description") else v)
    if r.period_start and r.period_end and r.period_end < r.period_start:
        raise HTTPException(400, "The period ends before it starts")
    db.flush()
    return r


def delete_round(db: Session, r: MeDailyRound) -> None:
    if db.execute(select(func.count()).select_from(_live(r.id).subquery())).scalar_one():
        raise HTTPException(409, "This daily evaluation has reports; close it instead of deleting it")
    db.delete(r)
    db.flush()


def set_agenda(db: Session, r: MeDailyRound, items: list[AgendaItemIn]) -> MeDailyRound:
    """Replace the whole agenda (the editor sends every row)."""
    for a in items:
        if a.planned_start and a.planned_end and form.minutes(a.planned_end) <= form.minutes(a.planned_start):
            raise HTTPException(400, f"Day {a.day}, '{a.topic}': planned end must be after planned start")
    for old in list(r.agenda):
        db.delete(old)
    db.flush()
    positions: dict[int, int] = defaultdict(int)
    for a in items:
        positions[a.day] += 1
        db.add(MeDailyAgendaItem(round_id=r.id, day=a.day, position=positions[a.day], topic=a.topic.strip(), planned_start=a.planned_start, planned_end=a.planned_end))
    db.flush()
    db.refresh(r)
    return r


# ---- reports -------------------------------------------------------------------------------------


def _clean_sessions(rows: list[SessionRow]) -> list[dict]:
    out = []
    for s in rows:
        if not (s.topic or "").strip() and not s.delivered and not s.actual_start:
            continue  # an untouched blank row
        d = {"topic": s.topic.strip(), "planned_start": s.planned_start or None, "planned_end": s.planned_end or None, "actual_start": s.actual_start or None,
             "actual_end": s.actual_end or None, "delivered": s.delivered, "reason": (s.reason or "").strip() or None}
        d["delta"] = form.session_delta(d)
        out.append(d)
    return out


def _apply(rep: Report, body: ReportIn) -> None:
    sessions = _clean_sessions(body.sessions)
    issues = [m.model_dump() for m in body.material_issues if (m.item or m.correction or "").strip() or m.type or m.severity]
    escalations = [x.model_dump() for x in body.escalations if (x.issue or x.raised_to or x.owner or "").strip()]
    d = {**body.model_dump(), "sessions": sessions, "material_issues": issues, "escalations": escalations}
    errors = form.validate(d)
    if errors:
        raise HTTPException(422, {"message": "Please check the form", "errors": errors})
    rep.phase = body.phase
    rep.platform_venue = body.platform_venue.strip()
    rep.class_hall = body.class_hall.strip()
    rep.training_day = body.training_day
    rep.report_date = body.report_date
    rep.lead_facilitator = body.lead_facilitator.strip()
    rep.co_facilitators = (body.co_facilitators or "").strip() or None
    rep.district = (body.district or "").strip() or None
    rep.sessions = json.dumps(sessions)
    rep.carried_over = json.dumps([t.strip() for t in body.carried_over if t.strip()])
    rep.quiz_administered = bool(body.quiz_administered)
    rep.quiz_title = (body.quiz_title or "").strip() or None if body.quiz_administered else None
    rep.mean_score = body.mean_score if body.quiz_administered else None
    rep.pass_rate = body.pass_rate if body.quiz_administered else None
    rep.quiz_comments = (body.quiz_comments or "").strip() or None
    rep.practice_minutes = body.practice_minutes
    rep.practice_comments = (body.practice_comments or "").strip() or None
    rep.hardest_topics = json.dumps([t.strip() for t in body.hardest_topics if t.strip()])
    rep.hardest_comments = (body.hardest_comments or "").strip() or None
    for key, _ in form.QUALITY:
        setattr(rep, f"q_{key}", getattr(body, f"q_{key}"))
        setattr(rep, f"q_{key}_evidence", (getattr(body, f"q_{key}_evidence") or "").strip() or None)
    rep.overall = round((body.q_content + body.q_engagement + body.q_time + body.q_illustrations) / 4, 2)
    rep.material_issues = json.dumps(issues)
    for key in ("internet", "power", "food"):
        setattr(rep, f"g_{key}", getattr(body, f"g_{key}"))
    rep.g_devices = body.g_devices or 0
    for key in ("internet", "power", "devices", "food"):
        setattr(rep, f"g_{key}_details", (getattr(body, f"g_{key}_details") or "").strip() or None)
    rep.escalations = json.dumps([{**x, "status": x.get("status") or "OPEN"} for x in escalations])


def public_submit(db: Session, r: MeDailyRound, body: PublicSubmitIn) -> PublicSubmitOut:
    if r.status != "OPEN":
        raise HTTPException(409, "This daily evaluation is closed")
    if body.report_date > date.today():
        raise HTTPException(400, "The report date cannot be in the future")
    rep = None
    if body.report_id and body.edit_token:
        rep = db.get(Report, body.report_id)
        if rep is None or rep.round_id != r.id or rep.deleted or rep.edit_token_hash != _hash(body.edit_token):
            raise HTTPException(403, "This report cannot be edited from this device; send a new one")
    token = body.edit_token if rep is not None else secrets.token_urlsafe(24)
    if rep is None:
        rep = Report(round_id=r.id, submitted_at=_now(), edit_token_hash=_hash(token))
        db.add(rep)
    _apply(rep, ReportIn(**body.model_dump(exclude={"edit_token", "report_id"})))
    db.flush()
    return PublicSubmitOut(report_id=rep.id, edit_token=token, submitted_at=rep.submitted_at, overall=rep.overall)


def get_report(db: Session, round_id: int, report_id: int) -> Report:
    rep = db.get(Report, report_id)
    if rep is None or rep.round_id != round_id or rep.deleted:
        raise HTTPException(404, "Report not found")
    return rep


def edit_report(db: Session, user: User, rep: Report, body: ReportIn) -> Report:
    _apply(rep, body)
    rep.edited_by = user.id
    db.flush()
    return rep


def set_escalation_status(db: Session, user: User, rep: Report, index: int, status: str) -> Report:
    rows = json.loads(rep.escalations)
    if index >= len(rows):
        raise HTTPException(404, "Escalation not found")
    rows[index]["status"] = status
    rep.escalations = json.dumps(rows)
    rep.edited_by = user.id
    db.flush()
    return rep


def delete_report(db: Session, rep: Report) -> None:
    rep.deleted = True
    db.flush()


def report_out(rep: Report, editors: dict[int, str] | None = None) -> ReportOut:
    sessions = [SessionRow(**s) for s in json.loads(rep.sessions)]
    esc = [Escalation(**x) for x in json.loads(rep.escalations)]
    deltas = [s.delta for s in sessions if s.delta is not None]
    return ReportOut(
        id=rep.id, round_id=rep.round_id, phase=rep.phase, phase_label=form.label("phase", rep.phase), platform_venue=rep.platform_venue, class_hall=rep.class_hall,
        training_day=rep.training_day, report_date=rep.report_date, lead_facilitator=rep.lead_facilitator, co_facilitators=rep.co_facilitators, district=rep.district,
        sessions=sessions, sessions_planned=len(sessions), sessions_delivered=sum(1 for s in sessions if s.delivered == "Y"), sessions_partly=sum(1 for s in sessions if s.delivered == "P"),
        sessions_not=sum(1 for s in sessions if s.delivered == "N"), minutes_delta=sum(deltas) if deltas else None, carried_over=json.loads(rep.carried_over),
        quiz_administered=rep.quiz_administered, quiz_title=rep.quiz_title, mean_score=rep.mean_score, pass_rate=rep.pass_rate, quiz_comments=rep.quiz_comments,
        practice_minutes=rep.practice_minutes, practice_comments=rep.practice_comments, hardest_topics=json.loads(rep.hardest_topics), hardest_comments=rep.hardest_comments,
        q_content=rep.q_content, q_content_evidence=rep.q_content_evidence, q_engagement=rep.q_engagement, q_engagement_evidence=rep.q_engagement_evidence,
        q_time=rep.q_time, q_time_evidence=rep.q_time_evidence, q_illustrations=rep.q_illustrations, q_illustrations_evidence=rep.q_illustrations_evidence,
        overall=rep.overall, low_scores=sum(1 for v in (rep.q_content, rep.q_engagement, rep.q_time, rep.q_illustrations) if v <= 2),
        material_issues=[MaterialIssue(**m) for m in json.loads(rep.material_issues)],
        g_internet=rep.g_internet, g_internet_details=rep.g_internet_details, g_power=rep.g_power, g_power_details=rep.g_power_details,
        g_devices=rep.g_devices, g_devices_details=rep.g_devices_details, g_food=rep.g_food, g_food_details=rep.g_food_details,
        escalations=esc, open_escalations=sum(1 for x in esc if x.status != "RESOLVED"),
        submitted_at=rep.submitted_at, updated_at=rep.updated_at, edited_by_name=(editors or {}).get(rep.edited_by) if rep.edited_by else None,
    )


def list_reports(db: Session, round_id: int, district: str | None = None, class_hall: str | None = None, facilitator: str | None = None,
                 phase: str | None = None, date_from: date | None = None, date_to: date | None = None) -> list[Report]:
    q = _live(round_id)
    if district:
        q = q.where(Report.district == district)
    if class_hall:
        q = q.where(func.lower(Report.class_hall) == class_hall.strip().lower())
    if facilitator:
        q = q.where(func.lower(Report.lead_facilitator) == facilitator.strip().lower())
    if phase:
        q = q.where(Report.phase == phase)
    if date_from:
        q = q.where(Report.report_date >= date_from)
    if date_to:
        q = q.where(Report.report_date <= date_to)
    return db.execute(q.order_by(Report.report_date.desc(), Report.training_day.desc(), Report.class_hall)).scalars().all()


def editors(db: Session, rows: list[Report]) -> dict[int, str]:
    ids = {x.edited_by for x in rows if x.edited_by}
    if not ids:
        return {}
    return {u.id: u.full_name for u in db.execute(select(User).where(User.id.in_(ids))).scalars()}


# ---- summary -------------------------------------------------------------------------------------


def _counts(values: list, pairs: list[tuple], total: int) -> list[CountRow]:
    c = defaultdict(int)
    for v in values:
        c[v] += 1
    return [CountRow(code=str(code), label=lb, count=c[code], pct=_pct(c[code], total) or 0.0) for code, lb in pairs]


def _group(rows: list[Report], key, label) -> list[GroupRow]:
    groups: dict[str, list[Report]] = defaultdict(list)
    for x in rows:
        groups[str(key(x))].append(x)
    out = []
    for k, items in groups.items():
        sessions = [s for x in items for s in json.loads(x.sessions)]
        issues = [m for x in items for m in json.loads(x.material_issues)]
        esc = [e for x in items for e in json.loads(x.escalations)]
        quizzes = [x for x in items if x.quiz_administered]
        out.append(GroupRow(
            key=k, label=label(items[0]), reports=len(items), sessions=len(sessions),
            delivered=sum(1 for s in sessions if s.get("delivered") == "Y"), partly=sum(1 for s in sessions if s.get("delivered") == "P"), not_delivered=sum(1 for s in sessions if s.get("delivered") == "N"),
            delivered_pct=_pct(sum(1 for s in sessions if s.get("delivered") == "Y"), len(sessions)), minutes_delta=sum(s.get("delta") or 0 for s in sessions),
            carried_over=sum(len(json.loads(x.carried_over)) for x in items), quizzes=len(quizzes), mean_score=_mean([x.mean_score for x in quizzes]), pass_rate=_mean([x.pass_rate for x in quizzes]),
            practice_minutes_avg=_mean([x.practice_minutes for x in items]),
            q_content=_mean([x.q_content for x in items]), q_engagement=_mean([x.q_engagement for x in items]), q_time=_mean([x.q_time for x in items]), q_illustrations=_mean([x.q_illustrations for x in items]),
            overall=_mean([x.overall for x in items]), low_scores=sum(1 for x in items if min(x.q_content, x.q_engagement, x.q_time, x.q_illustrations) <= 2),
            material_issues=len(issues), high_severity=sum(1 for m in issues if m.get("severity") == "H"),
            internet=_mean([x.g_internet for x in items]), power=_mean([x.g_power for x in items]), devices_short=sum(x.g_devices for x in items), food=_mean([x.g_food for x in items]),
            escalations=len(esc), open_escalations=sum(1 for e in esc if e.get("status") != "RESOLVED"),
        ))
    return out


def _log(x: Report, fields: dict) -> LogRow:
    return LogRow(report_id=x.id, report_date=x.report_date, training_day=x.training_day, class_hall=x.class_hall, district=x.district, lead_facilitator=x.lead_facilitator,
                  fields={k: (None if v is None else str(v)) for k, v in fields.items()})


def summary(db: Session, r: MeDailyRound, district: str | None = None, class_hall: str | None = None, facilitator: str | None = None,
            phase: str | None = None, date_from: date | None = None, date_to: date | None = None) -> Summary:
    rows = list_reports(db, r.id, district, class_hall, facilitator, phase, date_from, date_to)
    n = len(rows)
    sessions = [s for x in rows for s in json.loads(x.sessions)]
    issues = [(x, m) for x in rows for m in json.loads(x.material_issues)]
    esc = [(x, e) for x in rows for e in json.loads(x.escalations)]
    quizzes = [x for x in rows if x.quiz_administered]
    scale_pairs = [(v, f"{v} · {form.SCALE_SHORT[v]}") for v in (5, 4, 3, 2, 1)]
    ed = editors(db, rows)

    # topics: the agenda first (in order), then any topic typed on a form
    topic_stats: dict[str, dict] = {}
    for a in r.agenda:
        topic_stats.setdefault(a.topic.strip().lower(), {"topic": a.topic.strip(), "day": a.day, "planned": 0, "delivered": 0, "partly": 0, "not_delivered": 0, "minutes_delta": 0, "carried_over": 0, "hardest": 0})
    for x in rows:
        for s in json.loads(x.sessions):
            t = topic_stats.setdefault((s.get("topic") or "").strip().lower(), {"topic": (s.get("topic") or "").strip(), "day": None, "planned": 0, "delivered": 0, "partly": 0, "not_delivered": 0, "minutes_delta": 0, "carried_over": 0, "hardest": 0})
            t["planned"] += 1
            t["delivered" if s.get("delivered") == "Y" else "partly" if s.get("delivered") == "P" else "not_delivered"] += 1
            t["minutes_delta"] += s.get("delta") or 0
        for c in json.loads(x.carried_over):
            topic_stats.setdefault(c.strip().lower(), {"topic": c.strip(), "day": None, "planned": 0, "delivered": 0, "partly": 0, "not_delivered": 0, "minutes_delta": 0, "carried_over": 0, "hardest": 0})["carried_over"] += 1
        for h in json.loads(x.hardest_topics):
            topic_stats.setdefault(h.strip().lower(), {"topic": h.strip(), "day": None, "planned": 0, "delivered": 0, "partly": 0, "not_delivered": 0, "minutes_delta": 0, "carried_over": 0, "hardest": 0})["hardest"] += 1
    topics = [TopicRow(**t) for t in topic_stats.values() if t["planned"] or t["carried_over"] or t["hardest"] or t["day"] is not None]
    hardest = sorted([t for t in topics if t.hardest], key=lambda t: -t.hardest)

    evidence_log = []
    for x in rows:
        for key, lb in form.QUALITY:
            score = getattr(x, f"q_{key}")
            if score in form.EVIDENCE_SCORES:
                evidence_log.append(_log(x, {"criterion": lb[3:], "score": score, "evidence": getattr(x, f"q_{key}_evidence")}))

    return Summary(
        round=to_out(db, r),
        filters={"district": district, "class_hall": class_hall, "facilitator": facilitator, "phase": phase, "date_from": date_from.isoformat() if date_from else None, "date_to": date_to.isoformat() if date_to else None},
        reports=n, classes=len({x.class_hall.strip().lower() for x in rows}), days=len({x.training_day for x in rows}), facilitators=len({x.lead_facilitator.strip().lower() for x in rows}),
        districts=len({x.district or "" for x in rows}),
        sessions=len(sessions), delivered=sum(1 for s in sessions if s.get("delivered") == "Y"), partly=sum(1 for s in sessions if s.get("delivered") == "P"), not_delivered=sum(1 for s in sessions if s.get("delivered") == "N"),
        delivered_pct=_pct(sum(1 for s in sessions if s.get("delivered") == "Y"), len(sessions)), minutes_delta=sum(s.get("delta") or 0 for s in sessions),
        carried_over=sum(len(json.loads(x.carried_over)) for x in rows),
        quizzes=len(quizzes), mean_score=_mean([x.mean_score for x in quizzes]), pass_rate=_mean([x.pass_rate for x in quizzes]),
        practice_minutes_avg=_mean([x.practice_minutes for x in rows]), practice_na=sum(1 for x in rows if x.practice_minutes is None),
        quality={"content": _mean([x.q_content for x in rows]), "engagement": _mean([x.q_engagement for x in rows]), "time": _mean([x.q_time for x in rows]), "illustrations": _mean([x.q_illustrations for x in rows]), "overall": _mean([x.overall for x in rows])},
        quality_distribution={key: _counts([getattr(x, f"q_{key}") for x in rows], scale_pairs, n) for key, _ in form.QUALITY},
        overall_distribution=_counts([int(round(x.overall)) for x in rows], scale_pairs, n),
        low_scores=sum(1 for x in rows if min(x.q_content, x.q_engagement, x.q_time, x.q_illustrations) <= 2),
        material_issues=len(issues), issues_by_type=_counts([m.get("type") for _, m in issues], form.ISSUE_TYPES, len(issues)), issues_by_severity=_counts([m.get("severity") for _, m in issues], form.SEVERITIES, len(issues)),
        logistics={"internet": _mean([x.g_internet for x in rows]), "power": _mean([x.g_power for x in rows]), "food": _mean([x.g_food for x in rows])}, devices_short=sum(x.g_devices for x in rows),
        escalations=len(esc), open_escalations=sum(1 for _, e in esc if e.get("status") != "RESOLVED"), escalations_by_status=_counts([e.get("status") for _, e in esc], form.ESCALATION_STATUS, len(esc)),
        by_day=sorted(_group(rows, lambda x: x.training_day, lambda x: f"Day {x.training_day}"), key=lambda g: int(g.key)),
        by_class=sorted(_group(rows, lambda x: x.class_hall.strip().lower(), lambda x: x.class_hall.strip()), key=lambda g: g.label.lower()),
        by_district=sorted(_group(rows, lambda x: x.district or "", lambda x: x.district or "National / HQ"), key=lambda g: g.label),
        by_facilitator=sorted(_group(rows, lambda x: x.lead_facilitator.strip().lower(), lambda x: x.lead_facilitator.strip()), key=lambda g: g.label.lower()),
        by_phase=_group(rows, lambda x: x.phase, lambda x: form.label("phase", x.phase)),
        topics=topics, hardest_topics=[CountRow(code=t.topic, label=t.topic, count=t.hardest, pct=_pct(t.hardest, n) or 0.0) for t in hardest],
        issues_log=[_log(x, {"no": i + 1, "item": m.get("item"), "type": form.label("issue_type", m.get("type")), "severity": form.label("severity", m.get("severity")), "correction": m.get("correction")}) for x in rows for i, m in enumerate(json.loads(x.material_issues))],
        escalations_log=[_log(x, {"index": i, "issue": e.get("issue"), "raised_to": e.get("raised_to"), "owner": e.get("owner"), "needed_by": e.get("needed_by"), "status": e.get("status"), "status_label": form.label("status", e.get("status"))}) for x in rows for i, e in enumerate(json.loads(x.escalations))],
        evidence_log=evidence_log,
        carried_over_log=[_log(x, {"topic": c}) for x in rows for c in json.loads(x.carried_over)],
        latest=[report_out(x, ed) for x in rows],
    )


# ---- export --------------------------------------------------------------------------------------


def export(db: Session, r: MeDailyRound, **filters) -> report_service.Report:
    s = summary(db, r, **filters)
    g_headers = ["Group", "Reports", "Sessions", "Delivered (Y)", "Partly (P)", "Not delivered (N)", "Delivered %", "Minutes over/under", "Topics carried over", "Quizzes", "Mean score %", "Pass rate %",
                 "Practice min (avg)", "Content", "Engagement", "Time", "Illustrations", "Overall", "Reports scored 1–2", "Materials issues", "High severity", "Internet", "Power", "Devices short", "Food", "Escalations", "Open escalations"]

    def g_rows(groups: list[GroupRow]):
        return [[g.label, g.reports, g.sessions, g.delivered, g.partly, g.not_delivered, g.delivered_pct, g.minutes_delta, g.carried_over, g.quizzes, g.mean_score, g.pass_rate, g.practice_minutes_avg,
                 g.q_content, g.q_engagement, g.q_time, g.q_illustrations, g.overall, g.low_scores, g.material_issues, g.high_severity, g.internet, g.power, g.devices_short, g.food, g.escalations, g.open_escalations] for g in groups]

    summary_rows = [
        ["Reports", s.reports], ["Classes", s.classes], ["Training days", s.days], ["Lead facilitators", s.facilitators], ["Districts", s.districts],
        ["Sessions planned", s.sessions], ["Fully delivered (Y)", s.delivered], ["Partly delivered (P)", s.partly], ["Not delivered (N)", s.not_delivered], ["Delivered %", s.delivered_pct],
        ["Minutes over (+) / under (−), all sessions", s.minutes_delta], ["Topics carried to the next day", s.carried_over],
        ["Quizzes / assessments administered", s.quizzes], ["Mean score % (average)", s.mean_score], ["Pass rate % (average)", s.pass_rate],
        ["Practical / CAPI minutes (average)", s.practice_minutes_avg], ["Practice N/A (reports)", s.practice_na],
        *[[f"Facilitation quality: {lb[3:]} (mean 1–5)", s.quality[key]] for key, lb in form.QUALITY], ["Overall class rating (mean 1–5)", s.quality["overall"]], ["Reports with a criterion scored 1 or 2", s.low_scores],
        ["Materials and assessment issues", s.material_issues], *[[f"Issues: {c.label}", c.count] for c in s.issues_by_type], *[[f"Severity {c.label}", c.count] for c in s.issues_by_severity],
        ["Internet connectivity (mean 1–5)", s.logistics["internet"]], ["Power supply (mean 1–5)", s.logistics["power"]], ["Devices short (sum)", s.devices_short], ["Food & beverages (mean 1–5)", s.logistics["food"]],
        ["Escalations", s.escalations], ["Open escalations", s.open_escalations],
    ]
    rep_headers = ["Report", "Date", "Day", "Phase", "Platform / venue", "Class / hall", "District", "Lead facilitator", "Co-facilitators", "Sessions", "Delivered Y", "Partly P", "Not delivered N", "Minutes over/under",
                   "Carried to next day", "Quiz administered", "Quiz title", "Mean score %", "Pass rate %", "Quiz comments", "Practice minutes", "Practice comments", "Hardest topics", "Hardest comments",
                   "Content accuracy and clarity", "Evidence", "Participant engagement", "Evidence", "Time management", "Evidence", "Illustrations and practice", "Evidence", "Overall",
                   "Materials issues", "Internet", "Internet details", "Power", "Power details", "Devices short", "Devices details", "Food & beverages", "Food details", "Escalations", "Open escalations", "Submitted", "Edited by"]
    rep_rows = [[
        x.id, x.report_date, x.training_day, x.phase_label, x.platform_venue, x.class_hall, x.district or "National / HQ", x.lead_facilitator, x.co_facilitators or "", x.sessions_planned, x.sessions_delivered, x.sessions_partly, x.sessions_not,
        x.minutes_delta if x.minutes_delta is not None else "", "; ".join(x.carried_over), "Y" if x.quiz_administered else "N", x.quiz_title or "", x.mean_score if x.mean_score is not None else "", x.pass_rate if x.pass_rate is not None else "",
        x.quiz_comments or "", x.practice_minutes if x.practice_minutes is not None else "N/A", x.practice_comments or "", "; ".join(x.hardest_topics), x.hardest_comments or "",
        x.q_content, x.q_content_evidence or "", x.q_engagement, x.q_engagement_evidence or "", x.q_time, x.q_time_evidence or "", x.q_illustrations, x.q_illustrations_evidence or "", x.overall,
        len(x.material_issues), x.g_internet, x.g_internet_details or "", x.g_power, x.g_power_details or "", x.g_devices, x.g_devices_details or "", x.g_food, x.g_food_details or "", len(x.escalations), x.open_escalations, x.submitted_at, x.edited_by_name or "",
    ] for x in s.latest]
    session_rows = [[x.report_date, x.training_day, x.class_hall, x.district or "", x.lead_facilitator, sess.topic, sess.planned_start or "", sess.planned_end or "", sess.actual_start or "", sess.actual_end or "",
                     form.label("delivered", sess.delivered)[:1] if sess.delivered else "", sess.delta if sess.delta is not None else "", sess.reason or ""] for x in s.latest for sess in x.sessions]
    f = {k: v for k, v in s.filters.items() if v}
    base = ["Date", "Day", "Class / hall", "District", "Lead facilitator"]

    def log(rows: list[LogRow], keys: list[tuple[str, str]]):
        return [[l.report_date, l.training_day, l.class_hall, l.district or "", l.lead_facilitator] + [l.fields.get(k) or "" for k, _ in keys] for l in rows]

    return report_service.Report(
        kind="me_daily", title=f"Daily Facilitator Reports · {r.title}", generated_at=_now(), filters="; ".join(f"{k}={v}" for k, v in f.items()) or "none",
        sheets=[
            report_service.Sheet("Summary", ["Indicator", "Value"], summary_rows),
            report_service.Sheet("By day", g_headers, g_rows(s.by_day), landscape=True),
            report_service.Sheet("By class", g_headers, g_rows(s.by_class), landscape=True),
            report_service.Sheet("By district", g_headers, g_rows(s.by_district), landscape=True),
            report_service.Sheet("By facilitator", g_headers, g_rows(s.by_facilitator), landscape=True),
            report_service.Sheet("Topics", ["Topic", "Agenda day", "Sessions", "Delivered Y", "Partly P", "Not delivered N", "Minutes over/under", "Carried over", "Found hardest"],
                                 [[t.topic, t.day or "", t.planned, t.delivered, t.partly, t.not_delivered, t.minutes_delta, t.carried_over, t.hardest] for t in s.topics]),
            report_service.Sheet("Sessions", base + ["Session / topic", "Planned start", "Planned end", "Actual start", "Actual end", "Delivered", "Minutes over/under", "Reason"], session_rows, landscape=True),
            report_service.Sheet("Materials issues", base + ["No.", "Item", "Type", "Severity", "Proposed correction"], log(s.issues_log, [("no", ""), ("item", ""), ("type", ""), ("severity", ""), ("correction", "")]), landscape=True),
            report_service.Sheet("Escalations", base + ["Issue requiring management / CCIT action", "Raised to", "Proposed owner", "Needed by", "Status"], log(s.escalations_log, [("issue", ""), ("raised_to", ""), ("owner", ""), ("needed_by", ""), ("status_label", "")]), landscape=True),
            report_service.Sheet("Quality evidence", base + ["Criterion", "Score", "Evidence / justification"], log(s.evidence_log, [("criterion", ""), ("score", ""), ("evidence", "")]), landscape=True),
            report_service.Sheet("Reports", rep_headers, rep_rows, landscape=True),
        ],
    )
