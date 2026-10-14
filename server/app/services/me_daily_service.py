"""Daily Evaluation: rounds shared by link, the daily class reports lead trainers send, and the
summary (every detail, grouped by day, class, district, trainer and phase) with its export."""

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
from app.models import MeDailyReport, MeDailyRound, User
from app.schemas.me_daily import (
    ActionOut,
    ActionRow,
    CountRow,
    GroupRow,
    IssueRow,
    PublicSubmitIn,
    PublicSubmitOut,
    ReportIn,
    ReportOut,
    RoundIn,
    RoundOut,
    RoundUpdate,
    Summary,
)
from app.services import report_service


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _pct(n: int, d: int) -> float | None:
    return round(100.0 * n / d, 1) if d else None


def _rate(n: int, d: int) -> float | None:
    return _pct(n, d)


# ---- rounds ------------------------------------------------------------------------------------


def _live(round_id: int):
    return select(MeDailyReport).where(MeDailyReport.round_id == round_id, MeDailyReport.deleted.is_(False))


def to_out(db: Session, r: MeDailyRound) -> RoundOut:
    out = RoundOut.model_validate(r)
    base = settings.ME_PUBLIC_BASE_URL.rstrip("/")
    out.share_url = f"{base}/daily/{r.token}" if base else None
    rows = db.execute(_live(r.id)).scalars().all()
    out.reports = len(rows)
    out.classes = len({x.class_hall.strip().lower() for x in rows})
    out.days = len({x.training_day for x in rows})
    out.last_report_date = max((x.report_date for x in rows), default=None)
    out.attendance_rate = _rate(sum(x.present for x in rows), sum(x.expected for x in rows))
    out.major_gaps = sum(1 for x in rows if "MAJOR" in (x.delivery_content, x.delivery_participation, x.delivery_time))
    out.help_requests = sum(1 for x in rows if x.mgmt_help)
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
    r = MeDailyRound(
        title=body.title.strip(), phase=body.phase, period_start=body.period_start, period_end=body.period_end,
        description=(body.description or "").strip() or None, token=secrets.token_urlsafe(18), status="OPEN", created_by=user.id,
    )
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


# ---- reports -----------------------------------------------------------------------------------


def _apply(rep: MeDailyReport, body: ReportIn) -> None:
    d = body.model_dump()
    errors = form.validate(d)
    if errors:
        raise HTTPException(422, {"message": "Please check the form", "errors": errors})
    assessed = "NOT_ASSESSED" not in body.checks
    rep.report_date = body.report_date
    rep.training_day = body.training_day
    rep.class_hall = body.class_hall.strip()
    rep.venue = (body.venue or "").strip() or None
    rep.lead_trainer = body.lead_trainer.strip()
    rep.phase = body.phase
    rep.district = (body.district or "").strip() or None
    rep.expected, rep.present, rep.late = body.expected, body.present, body.late
    rep.coverage = body.coverage
    rep.incomplete_topic = (body.incomplete_topic or "").strip() or None if body.coverage != "ALL" else None
    rep.practice_not_scheduled = body.practice_not_scheduled
    rep.practice_minutes = None if body.practice_not_scheduled else body.practice_minutes
    rep.checks = ",".join(dict.fromkeys(c for c in body.checks if c in form.LABELS["check"]))
    rep.task_checked = (body.task_checked or "").strip() or None if assessed else None
    rep.number_checked = body.number_checked if assessed else None
    rep.number_met = body.number_met if assessed else None
    rep.criterion = (body.criterion or "").strip() or None if assessed else None
    rep.learning_gap = (body.learning_gap or "").strip() or None
    rep.followup_not_assessed = body.followup_not_assessed
    rep.followup_count = None if body.followup_not_assessed else body.followup_count
    rep.delivery_content, rep.delivery_participation, rep.delivery_time = body.delivery_content, body.delivery_participation, body.delivery_time
    rep.support = ",".join(dict.fromkeys(c for c in body.support if c in form.LABELS["support"]))
    rep.support_other = (body.support_other or "").strip() or None if "OTHER" in body.support else None
    rep.actions = json.dumps([a.model_dump() for a in body.actions if (a.issue or a.action or a.owner_due).strip()][: form.MAX_ACTIONS])
    rep.mgmt_help = body.mgmt_help
    rep.raised_to = (body.raised_to or "").strip() or None if body.mgmt_help else None


def public_submit(db: Session, r: MeDailyRound, body: PublicSubmitIn) -> PublicSubmitOut:
    if r.status != "OPEN":
        raise HTTPException(409, "This daily evaluation is closed")
    if r.period_end and body.report_date > date.today() and body.report_date > r.period_end:
        raise HTTPException(400, "The report date cannot be in the future")
    if body.report_date > date.today():
        raise HTTPException(400, "The report date cannot be in the future")
    rep = None
    if body.report_id and body.edit_token:
        rep = db.get(MeDailyReport, body.report_id)
        if rep is None or rep.round_id != r.id or rep.deleted or rep.edit_token_hash != _hash(body.edit_token):
            raise HTTPException(403, "This report cannot be edited from this device; send a new one")
    token = body.edit_token if rep is not None else secrets.token_urlsafe(24)
    if rep is None:
        rep = MeDailyReport(round_id=r.id, submitted_at=_now(), edit_token_hash=_hash(token))
        db.add(rep)
    _apply(rep, ReportIn(**body.model_dump(exclude={"edit_token", "report_id"})))
    db.flush()
    return PublicSubmitOut(report_id=rep.id, edit_token=token, submitted_at=rep.submitted_at)


def get_report(db: Session, round_id: int, report_id: int) -> MeDailyReport:
    rep = db.get(MeDailyReport, report_id)
    if rep is None or rep.round_id != round_id or rep.deleted:
        raise HTTPException(404, "Report not found")
    return rep


def edit_report(db: Session, user: User, rep: MeDailyReport, body: ReportIn) -> MeDailyReport:
    _apply(rep, body)
    rep.edited_by = user.id
    db.flush()
    return rep


def delete_report(db: Session, rep: MeDailyReport) -> None:
    rep.deleted = True
    db.flush()


def report_out(rep: MeDailyReport, editors: dict[int, str] | None = None) -> ReportOut:
    checks = [c for c in rep.checks.split(",") if c]
    support = [c for c in rep.support.split(",") if c]
    assessed = bool(checks) and "NOT_ASSESSED" not in checks
    return ReportOut(
        id=rep.id, round_id=rep.round_id, report_date=rep.report_date, training_day=rep.training_day, class_hall=rep.class_hall, venue=rep.venue,
        lead_trainer=rep.lead_trainer, phase=rep.phase, phase_label=form.label("phase", rep.phase), district=rep.district,
        expected=rep.expected, present=rep.present, late=rep.late, attendance_rate=_rate(rep.present, rep.expected),
        coverage=rep.coverage, coverage_label=form.label("coverage", rep.coverage), incomplete_topic=rep.incomplete_topic,
        practice_minutes=rep.practice_minutes, practice_not_scheduled=rep.practice_not_scheduled,
        checks=checks, checks_label=", ".join(form.label("check", c) for c in checks), assessed=assessed,
        task_checked=rep.task_checked, number_checked=rep.number_checked, number_met=rep.number_met,
        pass_rate=_rate(rep.number_met, rep.number_checked) if assessed and rep.number_checked else None,
        criterion=rep.criterion, learning_gap=rep.learning_gap, followup_count=rep.followup_count, followup_not_assessed=rep.followup_not_assessed,
        delivery_content=rep.delivery_content, delivery_participation=rep.delivery_participation, delivery_time=rep.delivery_time,
        major_gaps=sum(1 for v in (rep.delivery_content, rep.delivery_participation, rep.delivery_time) if v == "MAJOR"),
        support=support, support_label=", ".join(form.label("support", c) for c in support), support_other=rep.support_other,
        actions=[ActionRow(**a) for a in json.loads(rep.actions or "[]")], mgmt_help=rep.mgmt_help, raised_to=rep.raised_to,
        submitted_at=rep.submitted_at, updated_at=rep.updated_at, edited_by_name=(editors or {}).get(rep.edited_by) if rep.edited_by else None,
    )


def list_reports(db: Session, round_id: int, district: str | None = None, class_hall: str | None = None, trainer: str | None = None,
                 phase: str | None = None, date_from: date | None = None, date_to: date | None = None) -> list[MeDailyReport]:
    q = _live(round_id)
    if district:
        q = q.where(MeDailyReport.district == district)
    if class_hall:
        q = q.where(func.lower(MeDailyReport.class_hall) == class_hall.strip().lower())
    if trainer:
        q = q.where(func.lower(MeDailyReport.lead_trainer) == trainer.strip().lower())
    if phase:
        q = q.where(MeDailyReport.phase == phase)
    if date_from:
        q = q.where(MeDailyReport.report_date >= date_from)
    if date_to:
        q = q.where(MeDailyReport.report_date <= date_to)
    return db.execute(q.order_by(MeDailyReport.report_date.desc(), MeDailyReport.training_day.desc(), MeDailyReport.class_hall)).scalars().all()


def _editors(db: Session, rows: list[MeDailyReport]) -> dict[int, str]:
    ids = {x.edited_by for x in rows if x.edited_by}
    if not ids:
        return {}
    return {u.id: u.full_name for u in db.execute(select(User).where(User.id.in_(ids))).scalars()}


# ---- summary -----------------------------------------------------------------------------------


def _counts(values: list[str], pairs: list[tuple[str, str]], total: int) -> list[CountRow]:
    c = defaultdict(int)
    for v in values:
        c[v] += 1
    return [CountRow(code=code, label=lb, count=c[code], pct=_pct(c[code], total) or 0.0) for code, lb in pairs]


def _group(rows: list[MeDailyReport], key, label) -> list[GroupRow]:
    groups: dict[str, list[MeDailyReport]] = defaultdict(list)
    for x in rows:
        groups[str(key(x))].append(x)
    out = []
    for k, items in groups.items():
        expected = sum(x.expected for x in items)
        present = sum(x.present for x in items)
        late = sum(x.late for x in items)
        assessed = [x for x in items if x.checks and "NOT_ASSESSED" not in x.checks]
        checked = sum(x.number_checked or 0 for x in assessed)
        met = sum(x.number_met or 0 for x in assessed)
        agenda_all = sum(1 for x in items if x.coverage == "ALL")
        minutes = [x.practice_minutes for x in items if x.practice_minutes is not None]
        out.append(GroupRow(
            key=k, label=label(items[0]), reports=len(items), expected=expected, present=present, late=late,
            attendance_rate=_rate(present, expected), late_rate=_rate(late, present), agenda_all=agenda_all, agenda_all_pct=_pct(agenda_all, len(items)),
            assessed=len(assessed), checked=checked, met=met, pass_rate=_rate(met, checked), followup=sum(x.followup_count or 0 for x in items),
            major_gaps=sum(1 for x in items if "MAJOR" in (x.delivery_content, x.delivery_participation, x.delivery_time)),
            support_problems=sum(1 for x in items if x.support and x.support != "NONE"), help_requests=sum(1 for x in items if x.mgmt_help),
            practice_minutes_avg=round(sum(minutes) / len(minutes), 1) if minutes else None,
        ))
    return out


def summary(db: Session, r: MeDailyRound, district: str | None = None, class_hall: str | None = None, trainer: str | None = None,
            phase: str | None = None, date_from: date | None = None, date_to: date | None = None) -> Summary:
    rows = list_reports(db, r.id, district, class_hall, trainer, phase, date_from, date_to)
    n = len(rows)
    expected = sum(x.expected for x in rows)
    present = sum(x.present for x in rows)
    late = sum(x.late for x in rows)
    assessed = [x for x in rows if x.checks and "NOT_ASSESSED" not in x.checks]
    checked = sum(x.number_checked or 0 for x in assessed)
    met = sum(x.number_met or 0 for x in assessed)
    minutes = [x.practice_minutes for x in rows if x.practice_minutes is not None]
    check_values = [c for x in rows for c in x.checks.split(",") if c]
    support_values = [c for x in rows for c in x.support.split(",") if c]
    editors = _editors(db, rows)

    def issue(x: MeDailyReport, text: str, extra: str | None = None) -> IssueRow:
        return IssueRow(report_id=x.id, report_date=x.report_date, training_day=x.training_day, class_hall=x.class_hall, district=x.district, lead_trainer=x.lead_trainer, text=text, extra=extra)

    actions = []
    for x in rows:
        for a in json.loads(x.actions or "[]"):
            actions.append(ActionOut(report_id=x.id, report_date=x.report_date, training_day=x.training_day, class_hall=x.class_hall, district=x.district, lead_trainer=x.lead_trainer,
                                     issue=a.get("issue", ""), action=a.get("action", ""), owner_due=a.get("owner_due", "")))
    by_day = sorted(_group(rows, lambda x: x.training_day, lambda x: f"Day {x.training_day}"), key=lambda g: int(g.key))
    return Summary(
        round=to_out(db, r),
        filters={"district": district, "class_hall": class_hall, "trainer": trainer, "phase": phase, "date_from": date_from.isoformat() if date_from else None, "date_to": date_to.isoformat() if date_to else None},
        reports=n, classes=len({x.class_hall.strip().lower() for x in rows}), days=len({x.training_day for x in rows}),
        trainers=len({x.lead_trainer.strip().lower() for x in rows}), districts=len({x.district or "" for x in rows}),
        expected=expected, present=present, late=late, attendance_rate=_rate(present, expected), late_rate=_rate(late, present),
        coverage=_counts([x.coverage for x in rows], form.COVERAGE, n), agenda_all_pct=_pct(sum(1 for x in rows if x.coverage == "ALL"), n),
        practice_minutes_avg=round(sum(minutes) / len(minutes), 1) if minutes else None, practice_not_scheduled=sum(1 for x in rows if x.practice_not_scheduled),
        checks=_counts(check_values, form.CHECKS, n), assessed=len(assessed), checked=checked, met=met, pass_rate=_rate(met, checked),
        followup=sum(x.followup_count or 0 for x in rows), followup_not_assessed=sum(1 for x in rows if x.followup_not_assessed),
        delivery={key: _counts([getattr(x, f"delivery_{key}") for x in rows], form.RATINGS, n) for key, _ in form.DELIVERY_AREAS},
        reports_with_major_gaps=sum(1 for x in rows if "MAJOR" in (x.delivery_content, x.delivery_participation, x.delivery_time)),
        support=_counts(support_values, form.SUPPORT, n), help_requests=sum(1 for x in rows if x.mgmt_help), actions_total=len(actions),
        by_day=by_day,
        by_class=sorted(_group(rows, lambda x: x.class_hall.strip().lower(), lambda x: x.class_hall.strip()), key=lambda g: g.label.lower()),
        by_district=sorted(_group(rows, lambda x: x.district or "", lambda x: x.district or "National / HQ"), key=lambda g: g.label),
        by_trainer=sorted(_group(rows, lambda x: x.lead_trainer.strip().lower(), lambda x: x.lead_trainer.strip()), key=lambda g: g.label.lower()),
        by_phase=_group(rows, lambda x: x.phase, lambda x: form.label("phase", x.phase)),
        incomplete_topics=[issue(x, x.incomplete_topic) for x in rows if x.incomplete_topic],
        learning_gaps=[issue(x, x.learning_gap) for x in rows if x.learning_gap and x.learning_gap.strip().lower() != "none"],
        help_requested=[issue(x, x.raised_to or "", None) for x in rows if x.mgmt_help],
        actions=actions,
        latest=[report_out(x, editors) for x in rows],
    )


# ---- export ------------------------------------------------------------------------------------


def export(db: Session, r: MeDailyRound, **filters) -> report_service.Report:
    s = summary(db, r, **filters)
    g_headers = ["Group", "Reports", "Expected", "Present", "Attendance %", "Late", "Late %", "Agenda all topics", "Agenda all %", "Assessed", "Checked", "Met criterion", "Pass %",
                 "Needing follow-up", "Reports with Major gaps", "Reports with support problems", "Management help requests", "Practice minutes (avg)"]

    def g_rows(groups: list[GroupRow]):
        return [[g.label, g.reports, g.expected, g.present, g.attendance_rate, g.late, g.late_rate, g.agenda_all, g.agenda_all_pct, g.assessed, g.checked, g.met, g.pass_rate,
                 g.followup, g.major_gaps, g.support_problems, g.help_requests, g.practice_minutes_avg] for g in groups]

    summary_rows = [
        ["Reports", s.reports], ["Classes", s.classes], ["Training days", s.days], ["Lead trainers", s.trainers], ["Districts", s.districts],
        ["Expected trainees (sum of reports)", s.expected], ["Present", s.present], ["Attendance %", s.attendance_rate], ["Arrived late", s.late], ["Late %", s.late_rate],
        *[[f"Agenda: {c.label}", f"{c.count} ({c.pct}%)"] for c in s.coverage],
        ["Practice minutes (average)", s.practice_minutes_avg], ["Practice not scheduled (reports)", s.practice_not_scheduled],
        *[[f"Check used: {c.label}", f"{c.count} ({c.pct}%)"] for c in s.checks],
        ["Trainees checked", s.checked], ["Meeting the criterion", s.met], ["Pass %", s.pass_rate], ["Trainees needing follow-up", s.followup], ["Follow-up not assessed (reports)", s.followup_not_assessed],
        *[[f"{dict(form.DELIVERY_AREAS)[k]}: {c.label}", f"{c.count} ({c.pct}%)"] for k, rows_ in s.delivery.items() for c in rows_],
        ["Reports with at least one Major gaps", s.reports_with_major_gaps],
        *[[f"Support problem: {c.label}", f"{c.count} ({c.pct}%)"] for c in s.support],
        ["Management / CCIT help requested", s.help_requests], ["Priority actions recorded", s.actions_total],
    ]
    rep_headers = ["Report", "Date", "Day", "Class / hall", "Venue", "Lead trainer", "Phase", "District", "Expected", "Present", "Attendance %", "Late", "Agenda coverage", "Incomplete topic and reason",
                   "Practice minutes", "Practice not scheduled", "Check used", "Task / topic checked", "Number checked", "Number meeting criterion", "Pass %", "Criterion", "Main learning gap",
                   "Needing follow-up", "Follow-up not assessed", "Content accuracy and clarity", "Participation and use of practice", "Time management", "Support problems", "Other support problem",
                   "Action 1 issue", "Action 1 next action", "Action 1 owner and due", "Action 2 issue", "Action 2 next action", "Action 2 owner and due", "Management help", "Raised to", "Submitted", "Edited by"]
    rep_rows = []
    for x in s.latest:
        acts = (x.actions + [ActionRow(), ActionRow()])[:2]
        rep_rows.append([
            x.id, x.report_date, x.training_day, x.class_hall, x.venue or "", x.lead_trainer, x.phase_label, x.district or "National / HQ", x.expected, x.present, x.attendance_rate, x.late,
            x.coverage_label, x.incomplete_topic or "", x.practice_minutes if x.practice_minutes is not None else "", "Yes" if x.practice_not_scheduled else "", x.checks_label,
            x.task_checked or "", x.number_checked if x.number_checked is not None else "", x.number_met if x.number_met is not None else "", x.pass_rate, x.criterion or "", x.learning_gap or "",
            x.followup_count if x.followup_count is not None else "", "Yes" if x.followup_not_assessed else "", form.label("rating", x.delivery_content), form.label("rating", x.delivery_participation),
            form.label("rating", x.delivery_time), x.support_label, x.support_other or "", acts[0].issue, acts[0].action, acts[0].owner_due, acts[1].issue, acts[1].action, acts[1].owner_due,
            "Yes" if x.mgmt_help else "No", x.raised_to or "", x.submitted_at, x.edited_by_name or "",
        ])
    f = {k: v for k, v in s.filters.items() if v}
    return report_service.Report(
        kind="me_daily", title=f"Daily Evaluation · {r.title}", generated_at=_now(), filters="; ".join(f"{k}={v}" for k, v in f.items()) or "none",
        sheets=[
            report_service.Sheet("Summary", ["Measure", "Value"], summary_rows),
            report_service.Sheet("By day", g_headers, g_rows(s.by_day), landscape=True),
            report_service.Sheet("By class", g_headers, g_rows(s.by_class), landscape=True),
            report_service.Sheet("By district", g_headers, g_rows(s.by_district), landscape=True),
            report_service.Sheet("By trainer", g_headers, g_rows(s.by_trainer), landscape=True),
            report_service.Sheet("Priority actions", ["Date", "Day", "Class / hall", "District", "Lead trainer", "Issue and impact", "Next action", "Owner and due time"],
                                 [[a.report_date, a.training_day, a.class_hall, a.district or "", a.lead_trainer, a.issue, a.action, a.owner_due] for a in s.actions], landscape=True),
            report_service.Sheet("Learning gaps", ["Date", "Day", "Class / hall", "District", "Lead trainer", "Main learning gap or common error"],
                                 [[i.report_date, i.training_day, i.class_hall, i.district or "", i.lead_trainer, i.text] for i in s.learning_gaps]),
            report_service.Sheet("Incomplete topics", ["Date", "Day", "Class / hall", "District", "Lead trainer", "Topic and reason"],
                                 [[i.report_date, i.training_day, i.class_hall, i.district or "", i.lead_trainer, i.text] for i in s.incomplete_topics]),
            report_service.Sheet("Reports", rep_headers, rep_rows, landscape=True),
        ],
    )
