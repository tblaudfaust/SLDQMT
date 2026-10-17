"""Census Incident Log: what is reported, how it is handled, and what the dashboard shows."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class IncidentIn(BaseModel):
    """A new incident from a signed-in user."""

    district_id: int | None = None
    team_id: int | None = None
    sa_code: str | None = Field(default=None, max_length=16)
    ea_code: str | None = Field(default=None, max_length=16)
    locality: str | None = Field(default=None, max_length=200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    phase: str
    occurred_at: datetime
    category: str
    subcategory: str | None = None
    severity: str
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    action_taken: str | None = Field(default=None, max_length=3000)
    help_needed: str | None = Field(default=None, max_length=3000)
    teams_affected: int | None = Field(default=None, ge=0, le=100000)
    staff_affected: int | None = Field(default=None, ge=0, le=100000)
    households_affected: int | None = Field(default=None, ge=0, le=10000000)
    days_lost: int | None = Field(default=None, ge=0, le=365)
    asset_tags: str | None = Field(default=None, max_length=300)
    reference: str | None = Field(default=None, max_length=200)
    reporter_name: str | None = Field(default=None, max_length=160)  # on behalf of
    reporter_role: str | None = None
    reporter_phone: str | None = Field(default=None, max_length=32)


class PublicIncidentIn(BaseModel):
    """A supervisor's report from the public page: identified by the SA code."""

    sa_code: str = Field(min_length=12, max_length=12, pattern=r"^\d{12}$")
    reporter_name: str = Field(min_length=2, max_length=160)
    reporter_role: str = "SUPERVISOR"
    reporter_phone: str = Field(min_length=8, max_length=32)
    ea_code: str | None = Field(default=None, max_length=16)
    locality: str | None = Field(default=None, max_length=200)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    phase: str
    occurred_at: datetime
    category: str
    subcategory: str | None = None
    severity: str
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    action_taken: str | None = Field(default=None, max_length=3000)
    help_needed: str | None = Field(default=None, max_length=3000)
    teams_affected: int | None = Field(default=None, ge=0, le=100000)
    staff_affected: int | None = Field(default=None, ge=0, le=100000)
    households_affected: int | None = Field(default=None, ge=0, le=10000000)
    days_lost: int | None = Field(default=None, ge=0, le=365)
    asset_tags: str | None = Field(default=None, max_length=300)


class PublicIncidentOut(BaseModel):
    number: str
    track_token: str
    district: str | None = None
    sa_name: str | None = None
    sa_recognised: bool
    severity: str
    status: str


class PublicTrackOut(BaseModel):
    number: str
    title: str
    status: str
    status_label: str
    severity: str
    district: str | None = None
    reported_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution: str | None = None
    updates: list["UpdateOut"]


class SaCodeIn(BaseModel):
    sa_code: str = Field(min_length=12, max_length=12, pattern=r"^\d{12}$")
    district: str | None = None  # name or code
    team_code: str | None = None
    sa_name: str | None = None
    supervisor_name: str | None = None
    supervisor_phone: str | None = None


class SaCodeOut(BaseModel):
    id: int
    sa_code: str
    district_id: int | None = None
    district: str | None = None
    team_id: int | None = None
    team_code: str | None = None
    sa_name: str | None = None
    supervisor_name: str | None = None
    supervisor_phone: str | None = None
    active: bool


class SaCodeImportOut(BaseModel):
    created: int
    updated: int
    unknown_district: int
    errors: list[str]


class UpdateOut(BaseModel):
    id: int
    at: datetime
    author: str | None = None
    type: str
    type_label: str
    text: str | None = None
    old_value: str | None = None
    new_value: str | None = None


class IncidentOut(BaseModel):
    id: int
    number: str
    status: str
    status_label: str
    severity: str
    severity_label: str
    category: str
    category_label: str
    subcategory: str | None = None
    subcategory_label: str | None = None
    phase: str
    phase_label: str
    title: str
    description: str
    action_taken: str | None = None
    help_needed: str | None = None
    district_id: int | None = None
    district: str | None = None
    region: str | None = None
    team_id: int | None = None
    team_code: str | None = None
    sa_code: str | None = None
    sa_recognised: bool
    ea_code: str | None = None
    locality: str | None = None
    lat: float | None = None
    lng: float | None = None
    occurred_at: datetime
    reported_at: datetime
    reported_by_name: str | None = None
    reporter_name: str | None = None
    reporter_role: str | None = None
    reporter_role_label: str | None = None
    reporter_phone: str | None = None
    teams_affected: int | None = None
    staff_affected: int | None = None
    households_affected: int | None = None
    days_lost: int | None = None
    asset_tags: str | None = None
    reference: str | None = None
    level: str
    owner_id: int | None = None
    owner_name: str | None = None
    due_at: datetime | None = None
    overdue: bool
    unacknowledged_hours: float | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    resolution: str | None = None
    root_cause_fixed: bool | None = None
    lessons: str | None = None
    reject_reason: str | None = None
    hours_to_acknowledge: float | None = None
    hours_to_resolve: float | None = None
    updates: list[UpdateOut] = []


class IncidentEdit(BaseModel):
    """What a manager may change after the report."""

    district_id: int | None = None
    team_id: int | None = None
    category: str | None = None
    subcategory: str | None = None
    severity: str | None = None
    phase: str | None = None
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    ea_code: str | None = None
    locality: str | None = None
    asset_tags: str | None = None
    reference: str | None = None
    teams_affected: int | None = None
    staff_affected: int | None = None
    households_affected: int | None = None
    days_lost: int | None = None
    due_at: datetime | None = None


class ActionIn(BaseModel):
    """One handling action: acknowledge, assign, start, resolve, close, reject, reopen, escalate, comment."""

    action: str = Field(pattern="^(acknowledge|assign|start|resolve|close|reject|reopen|escalate|comment)$")
    text: str | None = Field(default=None, max_length=3000)
    owner_id: int | None = None
    level: str | None = Field(default=None, pattern="^(DISTRICT|REGION|NATIONAL)$")
    root_cause_fixed: bool | None = None
    lessons: str | None = Field(default=None, max_length=3000)
    due_at: datetime | None = None


class CountRow(BaseModel):
    code: str
    label: str
    count: int
    pct: float


class DistrictRow(BaseModel):
    district_id: int
    district: str
    region: str
    open: int
    new: int
    critical_open: int
    overdue: int
    resolved: int
    total: int
    per_100_eas: float | None = None
    median_hours_to_resolve: float | None = None


class TrendRow(BaseModel):
    day: date
    reported: int
    resolved: int
    open_end_of_day: int


class CategoryRow(BaseModel):
    category: str
    label: str
    total: int
    open: int
    critical: int
    major: int
    minor: int
    last_7_days: int
    previous_7_days: int


class SaRow(BaseModel):
    sa_code: str | None = None
    team_code: str | None = None
    district: str | None = None
    incidents: int
    open: int
    critical: int


class OwnerRow(BaseModel):
    owner_id: int | None = None
    owner: str
    open: int
    overdue: int
    resolved: int


class Dashboard(BaseModel):
    scope: str
    filters: dict[str, str | None]
    total: int
    open: int
    new_unacknowledged: int
    critical_open: int
    overdue: int
    due_today: int
    reported_today: int
    reported_7_days: int
    resolved_7_days: int
    closed: int
    rejected: int
    unrecognised_sa: int
    hours_to_acknowledge_median: float | None = None
    hours_to_resolve_median: float | None = None
    by_status: list[CountRow]
    by_severity: list[CountRow]
    by_phase: list[CountRow]
    by_level: list[CountRow]
    by_reporter_role: list[CountRow]
    by_category: list[CategoryRow]
    by_subcategory: list[CountRow]
    by_district: list[DistrictRow]
    by_owner: list[OwnerRow]
    top_sas: list[SaRow]
    trend: list[TrendRow]
    needs_action: list[IncidentOut]  # new, critical open, overdue — oldest first
    recent: list[IncidentOut]
    points: list[dict]  # lat, lng, severity, number, status for the map


class PersonOut(BaseModel):
    id: int
    full_name: str
    role: str
    district_ids: list[int] = []
