from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.dqm_report import ReportPeriod, ReportStatus
from app.schemas.common import ORMModel

# Fixed row labels from Annex A, so summaries can count by band and type.
ERROR_BANDS = {
    "LOW": "Reinterviews <5% discrepancy (Low)",
    "MEDIUM": "Reinterviews 5-10% discrepancy (Medium)",
    "HIGH": "Reinterviews >10% discrepancy (High)",
}
ISSUE_TYPES = {
    "OUTLIER": "Question response outliers",
    "GPS": "GPS / coordinate difficulty",
    "SYNC": "Synchronisation issue (Bluetooth or server)",
}
QUALITY_AREAS = {
    "GPS": "GPS use",
    "REINTERVIEW": "Supervisor re-interview",
    "CAPI": "CAPI, dashboard and synchronisation",
}
RESOLUTION_STATUSES = ("OPEN", "IN_PROGRESS", "RESOLVED")


class ErrorProfileRow(BaseModel):
    band: str = Field(pattern="^(LOW|MEDIUM|HIGH)$")
    ea_code: str = ""
    team: str = ""
    likely_cause: str = ""
    correction: str = ""
    remarks: str = ""


class SystemIssueRow(BaseModel):
    issue_type: str = Field(pattern="^(OUTLIER|GPS|SYNC)$")
    ea_code: str = ""
    finding: str = ""
    referred_to: str = ""
    action_taken: str = ""
    resolution_status: str = Field(default="OPEN", pattern="^(OPEN|IN_PROGRESS|RESOLVED)$")


class LessonRow(BaseModel):
    quality_area: str = Field(pattern="^(GPS|REINTERVIEW|CAPI)$")
    lesson: str = ""
    risk: str = ""
    control: str = ""


class SaPerformanceRow(BaseModel):
    sa: str = ""
    assessment: str = ""


class DqmReportIn(BaseModel):
    district_id: int | None = None  # district users: taken from their scope
    report_date: date
    period: ReportPeriod
    day_number: int = Field(ge=1, le=120)
    teams_reviewed: int | None = Field(default=None, ge=0)
    teams_certified: int | None = Field(default=None, ge=0)
    teams_pending: int | None = Field(default=None, ge=0)
    executive_summary: str | None = None
    reinterviews_received: int | None = Field(default=None, ge=0)
    reinterviews_received_pending: int | None = Field(default=None, ge=0)
    reinterviews_received_remarks: str | None = None
    reinterviews_certified: int | None = Field(default=None, ge=0)
    reinterviews_certified_pending: int | None = Field(default=None, ge=0)
    reinterviews_certified_remarks: str | None = None
    error_profile: list[ErrorProfileRow] = []
    system_issues: list[SystemIssueRow] = []
    lessons: list[LessonRow] = []
    sa_performance: list[SaPerformanceRow] = []
    prepared_name: str | None = None


class DqmReportOut(ORMModel):
    id: int
    district_id: int
    district: str = ""
    region_id: int | None = None
    region: str = ""
    report_date: date
    period: ReportPeriod
    day_number: int
    status: ReportStatus
    teams_reviewed: int | None
    teams_certified: int | None
    teams_pending: int | None = None
    executive_summary: str | None
    reinterviews_received: int | None
    reinterviews_received_pending: int | None
    reinterviews_received_remarks: str | None
    reinterviews_certified: int | None
    reinterviews_certified_pending: int | None
    reinterviews_certified_remarks: str | None
    error_profile: list[ErrorProfileRow] = []
    system_issues: list[SystemIssueRow] = []
    lessons: list[LessonRow] = []
    sa_performance: list[SaPerformanceRow] = []
    prepared_by: int | None
    prepared_name: str | None
    submitted_at: datetime | None
    received_by: int | None
    received_name: str | None
    received_at: datetime | None
    receiver_comment: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    delete_reason: str | None = None


class DqmReportListRow(BaseModel):
    id: int
    district_id: int
    district: str
    region: str
    report_date: date
    period: ReportPeriod
    day_number: int
    status: ReportStatus
    teams_reviewed: int | None
    teams_certified: int | None
    teams_pending: int | None = None
    reinterviews_received: int | None
    reinterviews_certified: int | None
    high_errors: int
    open_issues: int
    prepared_name: str | None
    created_by: int
    submitted_at: datetime | None
    received_at: datetime | None
    deleted_at: datetime | None = None


class ReceiveIn(BaseModel):
    comment: str | None = None


class DeleteIn(BaseModel):
    reason: str


class SummaryRow(BaseModel):
    key: int
    label: str  # district or region name
    reports: int
    submitted: int
    received: int
    days_covered: int
    latest_date: date | None
    teams_reviewed: int | None  # latest cumulative figure
    teams_certified: int | None
    teams_pending: int | None = None
    reinterviews_received: int
    reinterviews_received_pending: int
    reinterviews_certified: int
    reinterviews_certified_pending: int
    errors_low: int
    errors_medium: int
    errors_high: int
    issues_outlier: int
    issues_gps: int
    issues_sync: int
    issues_open: int
    lessons: int


class DqmSummary(BaseModel):
    level: str  # national | region
    region_id: int | None
    region: str | None
    date_from: date | None
    date_to: date | None
    rows: list[SummaryRow]
    totals: SummaryRow
    expected_units: int  # districts (region) or regions (national)
    reported_today: int
    missing_today: list[str]
    today: date
