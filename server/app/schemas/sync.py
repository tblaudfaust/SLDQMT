from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.error import ErrorStatus, SupportMethod
from app.schemas.common import ORMModel
from app.schemas.reference import ReferenceBundle


class ErrorIn(BaseModel):
    id: str = Field(min_length=36, max_length=36)
    display_id: str = Field(max_length=32)
    district_id: int
    team_id: int | None = None
    supervisor_id: int | None = None
    supervisor_name: str | None = None
    enumerator_id: int | None = None
    enumerator_name: str | None = None
    ea_id: int | None = None
    category_id: int
    source_id: int | None = None
    description: str = Field(min_length=1)
    date_received: date
    support_method: SupportMethod
    action_taken: str | None = None
    comments: str | None = None
    status: ErrorStatus
    resolved_at: datetime | None = None
    last_action_at: datetime
    lat: float | None = None
    lng: float | None = None
    accuracy_m: float | None = None
    gps_at: datetime | None = None
    client_created_at: datetime
    client_updated_at: datetime


class FollowUpIn(BaseModel):
    id: str = Field(min_length=36, max_length=36)
    error_id: str
    at: datetime
    method: SupportMethod
    contacted: str | None = None
    outcome: str | None = None
    comments: str | None = None
    lat: float | None = None
    lng: float | None = None
    accuracy_m: float | None = None
    gps_at: datetime | None = None
    client_created_at: datetime


class ActivityIn(BaseModel):
    id: str = Field(min_length=36, max_length=36)
    error_id: str
    previous_status: ErrorStatus | None = None
    new_status: ErrorStatus
    action_taken: str | None = None
    comments: str | None = None
    client_at: datetime


class PushRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=36)
    app_version: str | None = None
    pending_count: int = 0
    errors: list[ErrorIn] = []
    follow_ups: list[FollowUpIn] = []
    activity: list[ActivityIn] = []


class Receipt(BaseModel):
    kind: str  # error | follow_up | activity
    id: str
    result: str  # applied | duplicate | rejected
    reason: str | None = None
    version: int | None = None
    next_follow_up_at: datetime | None = None


class PushResponse(BaseModel):
    receipts: list[Receipt]
    applied: int
    duplicates: int
    rejected: int
    server_time: datetime


class FollowUpOut(ORMModel):
    id: str
    error_id: str
    at: datetime
    method: SupportMethod
    contacted: str | None = None
    outcome: str | None = None
    comments: str | None = None
    lat: float | None = None
    lng: float | None = None
    accuracy_m: float | None = None
    gps_at: datetime | None = None
    client_created_at: datetime
    server_at: datetime


class ActivityOut(ORMModel):
    id: str
    error_id: str
    previous_status: ErrorStatus | None = None
    new_status: ErrorStatus
    action_taken: str | None = None
    comments: str | None = None
    client_at: datetime
    server_at: datetime


class ErrorOut(ORMModel):
    id: str
    display_id: str
    user_id: int
    device_id: str | None = None
    district_id: int
    team_id: int | None = None
    supervisor_id: int | None = None
    supervisor_name: str | None = None
    enumerator_id: int | None = None
    enumerator_name: str | None = None
    ea_id: int | None = None
    category_id: int
    source_id: int | None = None
    description: str
    date_received: date
    support_method: SupportMethod
    action_taken: str | None = None
    comments: str | None = None
    status: ErrorStatus
    resolved_at: datetime | None = None
    last_action_at: datetime
    next_follow_up_at: datetime | None = None
    lat: float | None = None
    lng: float | None = None
    accuracy_m: float | None = None
    gps_at: datetime | None = None
    client_created_at: datetime
    client_updated_at: datetime
    server_updated_at: datetime
    version: int
    deleted_at: datetime | None = None
    delete_reason: str | None = None


class ErrorWithHistory(ErrorOut):
    follow_ups: list[FollowUpOut] = []
    activity: list[ActivityOut] = []


class PullResponse(BaseModel):
    cursor: str
    errors: list[ErrorWithHistory]
    reference: ReferenceBundle | None = None
    reference_version: str
    settings: dict[str, str]
    server_time: datetime
    more: bool
