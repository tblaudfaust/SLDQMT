"""Annex A daily DQM report: create, submit, receive, list, summarise, export."""

import json
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import District, DqmDailyReport, Region, ReportStatus, User
from app.models.user import Role
from app.schemas.dqm_report import (
    ERROR_BANDS,
    ISSUE_TYPES,
    QUALITY_AREAS,
    DqmReportIn,
    DqmReportListRow,
    DqmReportOut,
    DqmSummary,
    ErrorProfileRow,
    LessonRow,
    SaPerformanceRow,
    SummaryRow,
    SystemIssueRow,
)
from app.services import report_service
from app.services.scope import district_ids_for

JSON_FIELDS = {
    "error_profile": ErrorProfileRow,
    "system_issues": SystemIssueRow,
    "lessons": LessonRow,
    "sa_performance": SaPerformanceRow,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _loads(text: str | None, model) -> list:
    try:
        return [model.model_validate(x) for x in json.loads(text or "[]")]
    except (ValueError, TypeError):
        return []


def _geo(db: Session) -> tuple[dict[int, District], dict[int, Region]]:
    return {d.id: d for d in db.execute(select(District)).scalars()}, {r.id: r for r in db.execute(select(Region)).scalars()}


def to_out(db: Session, r: DqmDailyReport, districts=None, regions=None) -> DqmReportOut:
    if districts is None:
        districts, regions = _geo(db)
    d = districts.get(r.district_id)
    reg = regions.get(d.region_id) if d else None
    data = {c.key: getattr(r, c.key) for c in r.__table__.columns}
    for field, model in JSON_FIELDS.items():
        data[field] = _loads(getattr(r, field), model)
    data.update(district=d.name if d else "", region_id=reg.id if reg else None, region=reg.name if reg else "")
    return DqmReportOut.model_validate(data)


# ---- access -----------------------------------------------------------------


def _need(perms: set[str], code: str) -> None:
    if code not in perms:
        raise HTTPException(403, f"You do not have the right: {code}")


def resolve_district(db: Session, user: User, requested: int | None) -> int:
    scope = district_ids_for(db, user)
    if user.role == Role.DISTRICT_DQM:
        if not scope:
            raise HTTPException(403, "Your account has no district assigned")
        if requested is not None and requested not in scope:
            raise HTTPException(403, "You can only report for your own district")
        return requested if requested is not None else scope[0]
    if requested is None:
        raise HTTPException(400, "district_id is required")
    if scope is not None and requested not in scope:
        raise HTTPException(403, "District outside your scope")
    if db.get(District, requested) is None:
        raise HTTPException(404, "District not found")
    return requested


def get_in_scope(db: Session, user: User, report_id: int) -> DqmDailyReport:
    r = db.get(DqmDailyReport, report_id)
    scope = district_ids_for(db, user)
    if r is None or (scope is not None and r.district_id not in scope):
        raise HTTPException(404, "Report not found in your scope")
    return r


# ---- CRUD -------------------------------------------------------------------


def _apply(r: DqmDailyReport, body: DqmReportIn) -> None:
    data = body.model_dump(exclude={"district_id"})
    for field, model in JSON_FIELDS.items():
        data[field] = json.dumps([row.model_dump() for row in getattr(body, field)])
    for k, v in data.items():
        setattr(r, k, v)


def create(db: Session, user: User, perms: set[str], body: DqmReportIn) -> DqmDailyReport:
    _need(perms, "daily_reports.create")
    district_id = resolve_district(db, user, body.district_id)
    # Each DQM officer sends one report per district per day; other officers in the same district send their own.
    existing = db.execute(
        select(DqmDailyReport).where(
            DqmDailyReport.district_id == district_id, DqmDailyReport.report_date == body.report_date,
            DqmDailyReport.created_by == user.id, DqmDailyReport.deleted_at.is_(None),
        )
    ).scalars().first()
    if existing:
        raise HTTPException(409, f"Your report for this district on {body.report_date} already exists (id {existing.id}). Open that report instead of creating a new one.")
    if body.report_date > date.today():
        raise HTTPException(400, "The report date cannot be in the future")
    r = DqmDailyReport(district_id=district_id, created_by=user.id, status=ReportStatus.DRAFT)
    _apply(r, body)
    if not r.prepared_name:
        r.prepared_name = user.full_name
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def update(db: Session, user: User, perms: set[str], report_id: int, body: DqmReportIn) -> DqmDailyReport:
    _need(perms, "daily_reports.edit")
    r = get_in_scope(db, user, report_id)
    if r.deleted_at is not None:
        raise HTTPException(409, "This report is deleted; restore it first")
    if r.status == ReportStatus.RECEIVED:
        raise HTTPException(409, "This report has been received by National DQM and can no longer be edited")
    if user.role == Role.DISTRICT_DQM and r.created_by != user.id:
        raise HTTPException(403, "This report was prepared by another DQM officer. You can read it, but only edit and submit your own.")
    if body.district_id not in (None, r.district_id):
        raise HTTPException(400, "district cannot be changed")
    if body.report_date > date.today():
        raise HTTPException(400, "The report date cannot be in the future")
    if body.report_date != r.report_date:
        clash = db.execute(
            select(DqmDailyReport).where(
                DqmDailyReport.district_id == r.district_id, DqmDailyReport.report_date == body.report_date,
                DqmDailyReport.created_by == r.created_by, DqmDailyReport.id != r.id, DqmDailyReport.deleted_at.is_(None),
            )
        ).scalars().first()
        if clash:
            raise HTTPException(409, f"This officer's report for {body.report_date} already exists (id {clash.id})")
    _apply(r, body)
    db.commit()
    db.refresh(r)
    return r


def submit(db: Session, user: User, perms: set[str], report_id: int) -> DqmDailyReport:
    _need(perms, "daily_reports.submit")
    r = get_in_scope(db, user, report_id)
    if r.deleted_at is not None:
        raise HTTPException(409, "This report is deleted")
    if r.status == ReportStatus.RECEIVED:
        raise HTTPException(409, "Already received")
    if user.role == Role.DISTRICT_DQM and r.created_by != user.id:
        raise HTTPException(403, "This report was prepared by another DQM officer. You can read it, but only edit and submit your own.")
    r.status = ReportStatus.SUBMITTED
    r.prepared_by = user.id
    r.prepared_name = r.prepared_name or user.full_name
    r.submitted_at = _now()
    db.commit()
    db.refresh(r)
    return r


def receive(db: Session, user: User, perms: set[str], report_id: int, comment: str | None) -> DqmDailyReport:
    _need(perms, "daily_reports.receive")
    r = get_in_scope(db, user, report_id)
    if r.deleted_at is not None:
        raise HTTPException(409, "This report is deleted")
    if r.status == ReportStatus.DRAFT:
        raise HTTPException(409, "The district has not submitted this report yet")
    r.status = ReportStatus.RECEIVED
    r.received_by = user.id
    r.received_name = user.full_name
    r.received_at = _now()
    r.receiver_comment = comment
    db.commit()
    db.refresh(r)
    return r


def delete(db: Session, user: User, perms: set[str], report_id: int, reason: str) -> DqmDailyReport:
    _need(perms, "daily_reports.delete")
    r = get_in_scope(db, user, report_id)
    if r.deleted_at is not None:
        raise HTTPException(409, "Already deleted")
    if not reason.strip():
        raise HTTPException(400, "A reason is required")
    r.deleted_at = _now()
    r.deleted_by = user.id
    r.delete_reason = reason.strip()
    db.commit()
    db.refresh(r)
    return r


def restore(db: Session, user: User, perms: set[str], report_id: int) -> DqmDailyReport:
    _need(perms, "daily_reports.delete")
    r = get_in_scope(db, user, report_id)
    if r.deleted_at is None:
        raise HTTPException(409, "Not deleted")
    clash = db.execute(select(DqmDailyReport).where(DqmDailyReport.district_id == r.district_id, DqmDailyReport.report_date == r.report_date, DqmDailyReport.id != r.id, DqmDailyReport.deleted_at.is_(None))).scalars().first()
    if clash:
        raise HTTPException(409, f"Another report for {r.report_date} exists (id {clash.id}); delete it first")
    r.deleted_at = None
    r.deleted_by = None
    r.delete_reason = None
    db.commit()
    db.refresh(r)
    return r


def list_reports(
    db: Session, user: User, district_id: int | None, region_id: int | None, status: ReportStatus | None,
    date_from: date | None, date_to: date | None, deleted: bool = False,
) -> list[DqmReportListRow]:
    districts, regions = _geo(db)
    scope = district_ids_for(db, user)
    q = select(DqmDailyReport).order_by(DqmDailyReport.report_date.desc(), DqmDailyReport.district_id)
    q = q.where(DqmDailyReport.deleted_at.is_not(None)) if deleted else q.where(DqmDailyReport.deleted_at.is_(None))
    if scope is not None:
        q = q.where(DqmDailyReport.district_id.in_(scope))
    if district_id:
        q = q.where(DqmDailyReport.district_id == district_id)
    if region_id:
        q = q.where(DqmDailyReport.district_id.in_([d.id for d in districts.values() if d.region_id == region_id]))
    if status:
        q = q.where(DqmDailyReport.status == status)
    if date_from:
        q = q.where(DqmDailyReport.report_date >= date_from)
    if date_to:
        q = q.where(DqmDailyReport.report_date <= date_to)
    rows = []
    for r in db.execute(q).scalars():
        d = districts.get(r.district_id)
        errors = _loads(r.error_profile, ErrorProfileRow)
        issues = _loads(r.system_issues, SystemIssueRow)
        rows.append(
            DqmReportListRow(
                id=r.id, district_id=r.district_id, district=d.name if d else "", region=regions[d.region_id].name if d and d.region_id in regions else "",
                report_date=r.report_date, period=r.period, day_number=r.day_number, status=r.status,
                teams_reviewed=r.teams_reviewed, teams_certified=r.teams_certified, teams_pending=r.teams_pending,
                reinterviews_received=r.reinterviews_received, reinterviews_certified=r.reinterviews_certified,
                high_errors=sum(1 for e in errors if e.band == "HIGH"),
                open_issues=sum(1 for i in issues if i.resolution_status != "RESOLVED"),
                prepared_name=r.prepared_name, created_by=r.created_by, submitted_at=r.submitted_at, received_at=r.received_at, deleted_at=r.deleted_at,
            )
        )
    return rows


# ---- Summaries -------------------------------------------------------------


def _empty_row(key: int, label: str) -> SummaryRow:
    return SummaryRow(
        key=key, label=label, reports=0, submitted=0, received=0, days_covered=0, latest_date=None,
        teams_reviewed=None, teams_certified=None, teams_pending=None, reinterviews_received=0, reinterviews_received_pending=0,
        reinterviews_certified=0, reinterviews_certified_pending=0, errors_low=0, errors_medium=0, errors_high=0,
        issues_outlier=0, issues_gps=0, issues_sync=0, issues_open=0, lessons=0,
    )


def _accumulate(row: SummaryRow, r: DqmDailyReport, latest_by_unit: dict) -> None:
    row.reports += 1
    if r.status != ReportStatus.DRAFT:
        row.submitted += 1
    if r.status == ReportStatus.RECEIVED:
        row.received += 1
    row.reinterviews_received += r.reinterviews_received or 0
    row.reinterviews_received_pending += r.reinterviews_received_pending or 0
    row.reinterviews_certified += r.reinterviews_certified or 0
    row.reinterviews_certified_pending += r.reinterviews_certified_pending or 0
    for e in _loads(r.error_profile, ErrorProfileRow):
        if e.band == "LOW":
            row.errors_low += 1
        elif e.band == "MEDIUM":
            row.errors_medium += 1
        else:
            row.errors_high += 1
    for i in _loads(r.system_issues, SystemIssueRow):
        if i.issue_type == "OUTLIER":
            row.issues_outlier += 1
        elif i.issue_type == "GPS":
            row.issues_gps += 1
        else:
            row.issues_sync += 1
        if i.resolution_status != "RESOLVED":
            row.issues_open += 1
    row.lessons += len(_loads(r.lessons, LessonRow))
    # SAs reviewed/certified are cumulative per officer: take each officer's latest report in the
    # district and sum those (several DQM officers report on the same district).
    k = (r.district_id, r.created_by)
    latest = latest_by_unit.get(k)
    if latest is None or r.report_date > latest.report_date:
        latest_by_unit[k] = r


def summary(db: Session, user: User, level: str, region_id: int | None, date_from: date | None, date_to: date | None) -> DqmSummary:
    districts, regions = _geo(db)
    scope = district_ids_for(db, user)
    today = date.today()

    if level == "national":
        if user.role not in (Role.NATIONAL_DQM, Role.ADMIN):
            raise HTTPException(403, "The national summary is for National DQM")
        units = {reg.id: reg.name for reg in regions.values()}
        unit_of = lambda d: d.region_id  # noqa: E731
        in_scope_districts = list(districts.values())
        region_name = None
    else:
        if user.role == Role.REGIONAL:
            region_ids = {districts[d].region_id for d in (scope or []) if d in districts}
            if region_id is None and len(region_ids) == 1:
                region_id = next(iter(region_ids))
            if region_id not in region_ids:
                raise HTTPException(403, "Region outside your scope")
        if region_id is None:
            raise HTTPException(400, "region_id is required for a regional summary")
        if region_id not in regions:
            raise HTTPException(404, "Region not found")
        in_scope_districts = [d for d in districts.values() if d.region_id == region_id and (scope is None or d.id in scope)]
        units = {d.id: d.name for d in in_scope_districts}
        unit_of = lambda d: d.id  # noqa: E731
        region_name = regions[region_id].name

    q = select(DqmDailyReport).where(DqmDailyReport.district_id.in_([d.id for d in in_scope_districts]), DqmDailyReport.deleted_at.is_(None))
    if date_from:
        q = q.where(DqmDailyReport.report_date >= date_from)
    if date_to:
        q = q.where(DqmDailyReport.report_date <= date_to)
    reports = db.execute(q).scalars().all()

    rows = {k: _empty_row(k, v) for k, v in sorted(units.items(), key=lambda kv: kv[1])}
    latest_by_district: dict[tuple[int, int], DqmDailyReport] = {}
    days: dict[int, set] = {k: set() for k in rows}
    for r in reports:
        d = districts.get(r.district_id)
        if d is None:
            continue
        key = unit_of(d)
        if key not in rows:
            continue
        _accumulate(rows[key], r, latest_by_district)
        days[key].add(r.report_date)
    for key, row in rows.items():
        row.days_covered = len(days[key])
        row.latest_date = max(days[key]) if days[key] else None
        latest = [lr for (did, _officer), lr in latest_by_district.items() if unit_of(districts[did]) == key]
        if latest:
            row.teams_reviewed = sum(lr.teams_reviewed or 0 for lr in latest)
            row.teams_certified = sum(lr.teams_certified or 0 for lr in latest)
            row.teams_pending = sum(lr.teams_pending or 0 for lr in latest)

    totals = _empty_row(0, "Total")
    for row in rows.values():
        for f in ("reports", "submitted", "received", "reinterviews_received", "reinterviews_received_pending", "reinterviews_certified", "reinterviews_certified_pending", "errors_low", "errors_medium", "errors_high", "issues_outlier", "issues_gps", "issues_sync", "issues_open", "lessons"):
            setattr(totals, f, getattr(totals, f) + getattr(row, f))
        if row.teams_reviewed is not None:
            totals.teams_reviewed = (totals.teams_reviewed or 0) + row.teams_reviewed
            totals.teams_certified = (totals.teams_certified or 0) + (row.teams_certified or 0)
            totals.teams_pending = (totals.teams_pending or 0) + (row.teams_pending or 0)
    totals.days_covered = len({d for s in days.values() for d in s})
    totals.latest_date = max((r.latest_date for r in rows.values() if r.latest_date), default=None)

    reported = {r.district_id for r in reports if r.report_date == today and r.status != ReportStatus.DRAFT}
    missing = sorted(d.name for d in in_scope_districts if d.id not in reported)
    return DqmSummary(
        level=level, region_id=region_id, region=region_name, date_from=date_from, date_to=date_to,
        rows=list(rows.values()), totals=totals, expected_units=len(in_scope_districts),
        reported_today=len(reported), missing_today=missing, today=today,
    )


# ---- Export -----------------------------------------------------------------


def export_report(db: Session, user: User, report_id: int) -> report_service.Report:
    r = get_in_scope(db, user, report_id)
    out = to_out(db, r)
    fmt = lambda v: "" if v is None else v  # noqa: E731
    sheets = [
        report_service.Sheet(
            "Header", ["Field", "Value"],
            [["District", out.district], ["Region", out.region], ["Period", f"{out.period.value.title()} - Day {out.day_number}"],
             ["Report date", out.report_date.isoformat()], ["Status", out.status.value], ["Submitted to", "National Data Quality Manager (NDQM)"],
             ["Prepared by", fmt(out.prepared_name)], ["Submitted", report_service._fmt(out.submitted_at)],
             ["Received by", fmt(out.received_name)], ["Received", report_service._fmt(out.received_at)], ["Receiver comment", fmt(out.receiver_comment)]],
        ),
        report_service.Sheet(
            "1. Executive summary", ["Reporting area", "Cumulative assessment / summary"],
            [["Number of SAs reviewed", fmt(out.teams_reviewed)], ["Number of SAs certified", fmt(out.teams_certified)], ["Pending SAs", fmt(out.teams_pending)], ["Summary", fmt(out.executive_summary)]],
        ),
        report_service.Sheet(
            "2. Re-interview and certification", ["Indicator", "Final total", "Pending", "Affected EAs / remarks"],
            [["Reinterviews received for review", fmt(out.reinterviews_received), fmt(out.reinterviews_received_pending), fmt(out.reinterviews_received_remarks)],
             ["Reinterviews certified", fmt(out.reinterviews_certified), fmt(out.reinterviews_certified_pending), fmt(out.reinterviews_certified_remarks)]],
        ),
        report_service.Sheet(
            "3. Error and disparity profile", ["Error category", "EA code", "Team #", "Likely cause", "Correction / verification", "Remarks"],
            [[ERROR_BANDS[e.band], e.ea_code, e.team, e.likely_cause, e.correction, e.remarks] for e in out.error_profile], landscape=True,
        ),
        report_service.Sheet(
            "4. GIS, CAPI and synchronisation", ["Issue type", "EA code", "Finding", "Referred to", "Action taken", "Resolution status"],
            [[ISSUE_TYPES[i.issue_type], i.ea_code, i.finding, i.referred_to, i.action_taken, i.resolution_status.replace("_", " ").title()] for i in out.system_issues], landscape=True,
        ),
        report_service.Sheet(
            "5. Lessons and recommendations", ["Quality area", "Lesson / evidence", "Risk for enumeration", "Recommended control"],
            [[QUALITY_AREAS[l.quality_area], l.lesson, l.risk, l.control] for l in out.lessons], landscape=True,
        ),
        report_service.Sheet("6. Overall assessment", ["#", "Daily performance by SA"], [[i + 1, f"{p.sa}: {p.assessment}" if p.sa else p.assessment] for i, p in enumerate(out.sa_performance)]),
    ]
    return report_service.Report(
        kind="dqm_daily_report", title=f"DQM Daily Report - {out.district} - {out.report_date.isoformat()}",
        sheets=sheets, generated_at=_now(), filters=f"district={out.district}; date={out.report_date}",
    )


def export_summary(s: DqmSummary) -> report_service.Report:
    headers = ["Unit", "Reports", "Submitted", "Received", "Days", "Latest", "SAs reviewed", "SAs certified", "Pending SAs", "Reint. received", "Pending", "Reint. certified", "Pending", "Low", "Medium", "High", "Outliers", "GPS", "Sync", "Open issues", "Lessons"]
    def row(x: SummaryRow):
        return [x.label, x.reports, x.submitted, x.received, x.days_covered, x.latest_date.isoformat() if x.latest_date else "", x.teams_reviewed if x.teams_reviewed is not None else "", x.teams_certified if x.teams_certified is not None else "", x.teams_pending if x.teams_pending is not None else "", x.reinterviews_received, x.reinterviews_received_pending, x.reinterviews_certified, x.reinterviews_certified_pending, x.errors_low, x.errors_medium, x.errors_high, x.issues_outlier, x.issues_gps, x.issues_sync, x.issues_open, x.lessons]
    title = "DQM National Summary" if s.level == "national" else f"DQM Regional Summary - {s.region}"
    sheets = [
        report_service.Sheet("Summary", headers, [row(r) for r in s.rows] + [row(s.totals)], landscape=True),
        report_service.Sheet("Reporting today", ["Measure", "Value"], [["Districts expected", s.expected_units], ["Districts reported today", s.reported_today], ["Missing today", ", ".join(s.missing_today) or "none"]]),
    ]
    return report_service.Report(kind="dqm_summary", title=title, sheets=sheets, generated_at=_now(), filters=f"from={s.date_from or ''}; to={s.date_to or ''}")
