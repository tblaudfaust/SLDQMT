"""Chart-ready series for the Daily DQM reporting module at district, regional
and national level. Everything is computed from the Annex A reports in the
date range; teams reviewed and certified are cumulative per district, so a
day's figure is the sum of the reports filed that day (partial when some
districts have not reported)."""

from datetime import date, timedelta

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import District, DqmDailyReport, Region, ReportStatus, User
from app.models.user import Role
from app.schemas.dqm_report import ErrorProfileRow, LessonRow, SystemIssueRow
from app.services.dqm_report_service import _loads
from app.services.scope import district_ids_for


class TrendPoint(BaseModel):
    date: date
    reports: int
    teams_reviewed: int
    teams_certified: int
    reint_received: int
    reint_certified: int
    reint_pending: int
    low: int
    medium: int
    high: int
    outlier: int
    gps: int
    sync: int
    issues_open: int
    issues_resolved: int


class UnitPoint(BaseModel):
    key: int
    label: str
    reports: int
    submitted: int
    received: int
    days_covered: int
    teams_reviewed: int
    teams_certified: int
    reint_received: int
    reint_certified: int
    reint_pending: int
    low: int
    medium: int
    high: int
    outlier: int
    gps: int
    sync: int
    issues_open: int
    issues_resolved: int
    lessons: int


class DistrictPoint(UnitPoint):
    region_id: int
    region: str
    expected: int
    latest_date: date | None


class ComplianceRow(BaseModel):
    key: int
    label: str
    cells: list[str]  # one per day in `days`: NONE | DRAFT | SUBMITTED | RECEIVED


class Analytics(BaseModel):
    level: str
    unit_label: str
    title: str
    date_from: date
    date_to: date
    days: list[date]
    trend: list[TrendPoint]
    units: list[UnitPoint]
    districts: list[DistrictPoint]  # always per district, for the at-a-glance table
    compliance: list[ComplianceRow]
    totals: UnitPoint
    expected_reports: int
    submitted_reports: int


def _zero_unit(key: int, label: str) -> UnitPoint:
    return UnitPoint(key=key, label=label, reports=0, submitted=0, received=0, days_covered=0, teams_reviewed=0, teams_certified=0, reint_received=0, reint_certified=0, reint_pending=0, low=0, medium=0, high=0, outlier=0, gps=0, sync=0, issues_open=0, issues_resolved=0, lessons=0)


def _zero_trend(d: date) -> TrendPoint:
    return TrendPoint(date=d, reports=0, teams_reviewed=0, teams_certified=0, reint_received=0, reint_certified=0, reint_pending=0, low=0, medium=0, high=0, outlier=0, gps=0, sync=0, issues_open=0, issues_resolved=0)


def _add_counts(target, r: DqmDailyReport) -> None:
    target.reports += 1
    target.reint_received += r.reinterviews_received or 0
    target.reint_certified += r.reinterviews_certified or 0
    target.reint_pending += (r.reinterviews_received_pending or 0) + (r.reinterviews_certified_pending or 0)
    for e in _loads(r.error_profile, ErrorProfileRow):
        setattr(target, e.band.lower(), getattr(target, e.band.lower()) + 1)
    for i in _loads(r.system_issues, SystemIssueRow):
        setattr(target, i.issue_type.lower(), getattr(target, i.issue_type.lower()) + 1)
        if i.resolution_status == "RESOLVED":
            target.issues_resolved += 1
        else:
            target.issues_open += 1


def analytics(db: Session, user: User, level: str, district_id: int | None, region_id: int | None, date_from: date | None, date_to: date | None) -> Analytics:
    districts = {d.id: d for d in db.execute(select(District)).scalars()}
    regions = {r.id: r for r in db.execute(select(Region)).scalars()}
    scope = district_ids_for(db, user)
    date_to = date_to or date.today()
    date_from = date_from or date_to - timedelta(days=13)
    if date_from > date_to:
        raise HTTPException(400, "date_from must not be after date_to")
    if (date_to - date_from).days > 120:
        raise HTTPException(400, "At most 120 days at a time")

    if level == "national":
        if user.role not in (Role.NATIONAL_DQM, Role.ADMIN):
            raise HTTPException(403, "National analytics are for National DQM")
        in_scope = list(districts.values())
        units = {reg.id: reg.name for reg in regions.values()}
        unit_of = lambda d: d.region_id  # noqa: E731
        unit_label, title = "Region", "National"
    elif level == "region":
        if user.role == Role.REGIONAL:
            mine = {districts[d].region_id for d in (scope or []) if d in districts}
            if region_id is None and len(mine) == 1:
                region_id = next(iter(mine))
            if region_id not in mine:
                raise HTTPException(403, "Region outside your scope")
        if region_id is None or region_id not in regions:
            raise HTTPException(400, "region_id is required")
        in_scope = [d for d in districts.values() if d.region_id == region_id and (scope is None or d.id in scope)]
        units = {d.id: d.name for d in in_scope}
        unit_of = lambda d: d.id  # noqa: E731
        unit_label, title = "District", regions[region_id].name
    else:
        if district_id is None:
            if scope and len(scope) == 1:
                district_id = scope[0]
            else:
                raise HTTPException(400, "district_id is required")
        if district_id not in districts or (scope is not None and district_id not in scope):
            raise HTTPException(403, "District outside your scope")
        in_scope = [districts[district_id]]
        units = {district_id: districts[district_id].name}
        unit_of = lambda d: d.id  # noqa: E731
        unit_label, title = "District", districts[district_id].name

    q = select(DqmDailyReport).where(
        DqmDailyReport.district_id.in_([d.id for d in in_scope]),
        DqmDailyReport.report_date >= date_from,
        DqmDailyReport.report_date <= date_to,
        DqmDailyReport.deleted_at.is_(None),
    )
    reports = db.execute(q).scalars().all()

    days = [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]
    trend = {d: _zero_trend(d) for d in days}
    unit_points = {k: _zero_unit(k, v) for k, v in sorted(units.items(), key=lambda kv: kv[1])}
    district_points: dict[int, DistrictPoint] = {
        d.id: DistrictPoint(**_zero_unit(d.id, d.name).model_dump(), region_id=d.region_id, region=regions[d.region_id].name if d.region_id in regions else "", expected=len(days), latest_date=None)
        for d in sorted(in_scope, key=lambda x: x.name)
    }
    latest: dict[int, DqmDailyReport] = {}
    unit_days: dict[int, set] = {k: set() for k in unit_points}
    district_days: dict[int, set] = {d.id: set() for d in in_scope}
    compliance: dict[int, dict[date, str]] = {d.id: {} for d in in_scope}
    submitted_reports = 0

    for r in reports:
        d = districts.get(r.district_id)
        if d is None:
            continue
        t = trend[r.report_date]
        _add_counts(t, r)
        t.teams_reviewed += r.teams_reviewed or 0
        t.teams_certified += r.teams_certified or 0
        submitted = r.status != ReportStatus.DRAFT
        key = unit_of(d)
        if key in unit_points:
            u = unit_points[key]
            _add_counts(u, r)
            if submitted:
                u.submitted += 1
                submitted_reports += 1
            if r.status == ReportStatus.RECEIVED:
                u.received += 1
            u.lessons += len(_loads(r.lessons, LessonRow))
            unit_days[key].add(r.report_date)
        dp = district_points[r.district_id]
        _add_counts(dp, r)
        if submitted:
            dp.submitted += 1
        if r.status == ReportStatus.RECEIVED:
            dp.received += 1
        dp.lessons += len(_loads(r.lessons, LessonRow))
        district_days[r.district_id].add(r.report_date)
        prev = latest.get(r.district_id)
        if prev is None or r.report_date > prev.report_date:
            latest[r.district_id] = r
        compliance[r.district_id][r.report_date] = r.status.value

    for key, u in unit_points.items():
        u.days_covered = len(unit_days[key])
        for did, lr in latest.items():
            if unit_of(districts[did]) == key:
                u.teams_reviewed += lr.teams_reviewed or 0
                u.teams_certified += lr.teams_certified or 0
    for did, dp in district_points.items():
        dp.days_covered = len(district_days[did])
        dp.latest_date = max(district_days[did]) if district_days[did] else None
        lr = latest.get(did)
        if lr is not None:
            dp.teams_reviewed = lr.teams_reviewed or 0
            dp.teams_certified = lr.teams_certified or 0

    totals = _zero_unit(0, "Total")
    for u in unit_points.values():
        for f in ("reports", "submitted", "received", "teams_reviewed", "teams_certified", "reint_received", "reint_certified", "reint_pending", "low", "medium", "high", "outlier", "gps", "sync", "issues_open", "issues_resolved", "lessons"):
            setattr(totals, f, getattr(totals, f) + getattr(u, f))
    totals.days_covered = len({d for s in unit_days.values() for d in s})

    return Analytics(
        level=level, unit_label=unit_label, title=title, date_from=date_from, date_to=date_to, days=days,
        trend=list(trend.values()), units=list(unit_points.values()), districts=list(district_points.values()),
        compliance=[ComplianceRow(key=d.id, label=d.name, cells=[compliance[d.id].get(day, "NONE") for day in days]) for d in sorted(in_scope, key=lambda x: x.name)],
        totals=totals, expected_reports=len(in_scope) * len(days), submitted_reports=submitted_reports,
    )
