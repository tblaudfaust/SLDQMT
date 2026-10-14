"""Daily Evaluation: rounds, the lead trainer's daily class report and the summary the dashboard shows."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RoundIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    phase: str = Field(pattern="^(MASTER|TOT|FIELD)$")
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = Field(default=None, max_length=2000)


class RoundUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    phase: str | None = Field(default=None, pattern="^(MASTER|TOT|FIELD)$")
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, pattern="^(OPEN|CLOSED)$")


class RoundOut(ORMModel):
    id: int
    title: str
    phase: str
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = None
    token: str
    status: str
    created_at: datetime
    share_url: str | None = None
    reports: int = 0
    classes: int = 0
    days: int = 0
    last_report_date: date | None = None
    attendance_rate: float | None = None
    major_gaps: int = 0  # reports with at least one Major gaps rating
    help_requests: int = 0


class ActionRow(BaseModel):
    issue: str = Field(default="", max_length=1000)
    action: str = Field(default="", max_length=1000)
    owner_due: str = Field(default="", max_length=200)


class ReportIn(BaseModel):
    """The form as the lead trainer submits it (public page) or a manager edits it."""

    report_date: date
    training_day: int = Field(ge=1, le=60)
    class_hall: str = Field(min_length=1, max_length=80)
    venue: str | None = Field(default=None, max_length=160)
    lead_trainer: str = Field(min_length=2, max_length=160)
    phase: str = Field(pattern="^(MASTER|TOT|FIELD)$")
    district: str | None = Field(default=None, max_length=60)
    expected: int = Field(ge=0, le=5000)
    present: int = Field(ge=0, le=5000)
    late: int = Field(default=0, ge=0, le=5000)
    coverage: str = Field(pattern="^(ALL|SOME|NONE)$")
    incomplete_topic: str | None = Field(default=None, max_length=2000)
    practice_minutes: int | None = Field(default=None, ge=0, le=1440)
    practice_not_scheduled: bool = False
    checks: list[str] = []
    task_checked: str | None = Field(default=None, max_length=2000)
    number_checked: int | None = Field(default=None, ge=0, le=5000)
    number_met: int | None = Field(default=None, ge=0, le=5000)
    criterion: str | None = Field(default=None, max_length=2000)
    learning_gap: str | None = Field(default=None, max_length=2000)
    followup_count: int | None = Field(default=None, ge=0, le=5000)
    followup_not_assessed: bool = False
    delivery_content: str = Field(pattern="^(GOOD|SOME|MAJOR)$")
    delivery_participation: str = Field(pattern="^(GOOD|SOME|MAJOR)$")
    delivery_time: str = Field(pattern="^(GOOD|SOME|MAJOR)$")
    support: list[str] = []
    support_other: str | None = Field(default=None, max_length=1000)
    actions: list[ActionRow] = []
    mgmt_help: bool = False
    raised_to: str | None = Field(default=None, max_length=160)


class PublicSubmitIn(ReportIn):
    edit_token: str | None = None  # present when the same browser corrects a report it sent
    report_id: int | None = None


class PublicSubmitOut(BaseModel):
    report_id: int
    edit_token: str
    submitted_at: datetime


class ReportOut(BaseModel):
    """Every field of one report, with labels for the reports and the detail view."""

    id: int
    round_id: int
    report_date: date
    training_day: int
    class_hall: str
    venue: str | None = None
    lead_trainer: str
    phase: str
    phase_label: str
    district: str | None = None
    expected: int
    present: int
    late: int
    attendance_rate: float | None = None
    coverage: str
    coverage_label: str
    incomplete_topic: str | None = None
    practice_minutes: int | None = None
    practice_not_scheduled: bool
    checks: list[str]
    checks_label: str
    assessed: bool
    task_checked: str | None = None
    number_checked: int | None = None
    number_met: int | None = None
    pass_rate: float | None = None
    criterion: str | None = None
    learning_gap: str | None = None
    followup_count: int | None = None
    followup_not_assessed: bool
    delivery_content: str
    delivery_participation: str
    delivery_time: str
    major_gaps: int  # how many of the three areas are Major gaps
    support: list[str]
    support_label: str
    support_other: str | None = None
    actions: list[ActionRow]
    mgmt_help: bool
    raised_to: str | None = None
    submitted_at: datetime
    updated_at: datetime
    edited_by_name: str | None = None


class CountRow(BaseModel):
    code: str
    label: str
    count: int
    pct: float


class GroupRow(BaseModel):
    """Attendance, agenda, learning and delivery for one training day, class, district, trainer or phase."""

    key: str
    label: str
    reports: int
    expected: int
    present: int
    late: int
    attendance_rate: float | None = None
    late_rate: float | None = None
    agenda_all: int
    agenda_all_pct: float | None = None
    assessed: int
    checked: int
    met: int
    pass_rate: float | None = None
    followup: int
    major_gaps: int
    support_problems: int
    help_requests: int
    practice_minutes_avg: float | None = None


class IssueRow(BaseModel):
    report_id: int
    report_date: date
    training_day: int
    class_hall: str
    district: str | None = None
    lead_trainer: str
    text: str
    extra: str | None = None  # the next action, or the person it was raised to


class ActionOut(BaseModel):
    report_id: int
    report_date: date
    training_day: int
    class_hall: str
    district: str | None = None
    lead_trainer: str
    issue: str
    action: str
    owner_due: str


class Summary(BaseModel):
    round: RoundOut
    filters: dict[str, str | None]
    reports: int
    classes: int
    days: int
    trainers: int
    districts: int
    expected: int
    present: int
    late: int
    attendance_rate: float | None = None
    late_rate: float | None = None
    coverage: list[CountRow]
    agenda_all_pct: float | None = None
    practice_minutes_avg: float | None = None
    practice_not_scheduled: int
    checks: list[CountRow]
    assessed: int
    checked: int
    met: int
    pass_rate: float | None = None
    followup: int
    followup_not_assessed: int
    delivery: dict[str, list[CountRow]]  # content / participation / time → Good / Some / Major
    reports_with_major_gaps: int
    support: list[CountRow]
    help_requests: int
    actions_total: int
    by_day: list[GroupRow]
    by_class: list[GroupRow]
    by_district: list[GroupRow]
    by_trainer: list[GroupRow]
    by_phase: list[GroupRow]
    incomplete_topics: list[IssueRow]
    learning_gaps: list[IssueRow]
    help_requested: list[IssueRow]
    actions: list[ActionOut]
    latest: list[ReportOut]


class PublicRound(BaseModel):
    title: str
    phase: str
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = None
    status: str
    form: dict
