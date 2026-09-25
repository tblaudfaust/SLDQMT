from datetime import date, datetime

from pydantic import BaseModel

from app.models.error import ErrorStatus, SupportMethod


class Filters(BaseModel):
    district_id: list[int] | None = None
    team_id: int | None = None
    ea_id: int | None = None
    category_id: int | None = None
    status: ErrorStatus | None = None
    date_from: date | None = None
    date_to: date | None = None
    supervisor_id: int | None = None
    supervisor: str | None = None
    enumerator: str | None = None
    user_id: int | None = None
    support_method: SupportMethod | None = None
    overdue_only: bool = False
    search: str | None = None


class ErrorUpdate(BaseModel):
    """Fields a dashboard user may change on an error record."""

    team_id: int | None = None
    ea_id: int | None = None
    category_id: int | None = None
    source_id: int | None = None
    supervisor_name: str | None = None
    enumerator_name: str | None = None
    description: str | None = None
    date_received: date | None = None
    support_method: SupportMethod | None = None
    action_taken: str | None = None
    comments: str | None = None
    status: ErrorStatus | None = None
    note: str | None = None  # why the change was made; goes into the activity history


class DeleteIn(BaseModel):
    reason: str


class Summary(BaseModel):
    total: int
    resolved: int
    unresolved: int
    overdue: int
    resolution_rate: float
    median_days_to_resolve: float | None
    as_of: datetime
    last_sync_at: datetime | None


class Bucket(BaseModel):
    key: int | str | None
    label: str
    total: int
    resolved: int
    unresolved: int
    overdue: int


class TrendPoint(BaseModel):
    period: str
    received: int
    resolved: int


class AgeingBand(BaseModel):
    band: str
    count: int


class MonitorRow(BaseModel):
    user_id: int
    full_name: str
    districts: str
    total: int
    unresolved: int
    overdue: int
    last_sync_at: datetime | None
    last_activity_at: datetime | None
    app_version: str | None
    pending_reported: int


class TeamRow(BaseModel):
    team_id: int | None
    team: str
    district: str
    supervisor: str | None
    total: int
    resolved: int
    unresolved: int
    overdue: int


class OverdueRow(BaseModel):
    id: str
    display_id: str
    district: str
    team: str | None
    category: str
    supervisor_name: str | None
    monitor: str
    next_follow_up_at: datetime | None
    hours_overdue: float


class ErrorListRow(BaseModel):
    id: str
    display_id: str
    district: str
    team: str | None
    ea: str | None
    category: str
    supervisor_name: str | None
    enumerator_name: str | None
    description: str
    date_received: date
    support_method: SupportMethod
    status: ErrorStatus
    next_follow_up_at: datetime | None
    overdue: bool
    monitor: str
    last_action_at: datetime
    follow_up_count: int
