"""M&E Field Monitoring: what the tablet pushes and pulls, and what the dashboards read."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class GpsIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0)
    at: datetime | None = None


class VisitIn(BaseModel):
    """One completed form. `answers` holds every item by code (see app.core.mefm_form); the GPS
    fix the device captured comes separately and is also stored as A15."""

    id: str = Field(min_length=36, max_length=36)
    pop_ea_code: str = Field(min_length=1, max_length=16)
    answers: dict
    gps: GpsIn
    client_created_at: datetime
    client_updated_at: datetime


class CheckinIn(BaseModel):
    id: str = Field(min_length=36, max_length=36)
    chiefdom_code: str | None = None
    section_code: str | None = None
    note: str | None = Field(default=None, max_length=500)
    gps: GpsIn
    at: datetime


class MefmPushRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=36)
    app_version: str | None = None
    pending_count: int = 0
    visits: list[VisitIn] = []
    checkins: list[CheckinIn] = []


class MefmReceipt(BaseModel):
    kind: str  # visit | checkin
    id: str
    result: str  # applied | duplicate | rejected
    reason: str | None = None
    errors: list[str] = []  # validation messages, "<code>: message", when rejected for INVALID
    flags: list[str] = []
    version: int | None = None


class MefmPushResponse(BaseModel):
    receipts: list[MefmReceipt]
    applied: int
    duplicates: int
    rejected: int
    server_time: datetime


# Frame for the tablet (the officer's districts only)
class FrameDistrict(BaseModel):
    id: int
    code: str
    name: str
    region: str


class FrameChiefdom(BaseModel):
    id: int
    district_id: int
    code: str
    name: str


class FrameSection(BaseModel):
    id: int
    district_id: int
    chiefdom_id: int
    code: str
    name: str


class FrameTeam(BaseModel):
    id: int
    district_id: int
    code: str
    name: str
    chiefdom: str | None = None
    supervisor: str | None = None
    enumerators: list[str] = []


class FrameEa(BaseModel):
    id: int
    team_id: int
    code: str
    name: str | None = None
    locality: str | None = None
    pop_ea_code: str | None = None
    chiefdom_code: str | None = None
    section_code: str | None = None
    loc_status: str | None = None
    expected_households: int | None = None
    lat: float | None = None
    lng: float | None = None


class MefmFrame(BaseModel):
    version: str
    districts: list[FrameDistrict]
    chiefdoms: list[FrameChiefdom]
    sections: list[FrameSection]
    teams: list[FrameTeam]
    eas: list[FrameEa]


class VisitState(BaseModel):
    """What the tablet needs to know about a form it sent: received, reviewed, deleted, and its flags."""

    id: str
    status: str
    version: int
    flags: list[str] = []
    review_note: str | None = None
    open_issues: int = 0
    server_updated_at: datetime
    deleted: bool = False


class MefmPullResponse(BaseModel):
    cursor: str
    form: dict | None = None  # the questionnaire spec, when form_version differs
    form_version: str
    frame: MefmFrame | None = None  # when frame_version differs
    frame_version: str
    settings: dict[str, str]
    visits: list[VisitState]
    server_time: datetime
    more: bool
    pin_reset: bool = False


# Dashboard reads (stage 3 builds on these)
class IssueOut(ORMModel):
    id: int
    visit_id: str
    district_id: int
    question: str | None = None
    severity: str
    description: str
    action: str | None = None
    referred_to: str | None = None
    deadline: date | None = None
    auto: bool
    status: str
    resolution: str | None = None
    closed_at: datetime | None = None


class VisitRow(BaseModel):
    id: str
    user_id: int
    officer: str
    district_id: int
    district: str
    chiefdom: str | None = None
    section: str | None = None
    sa_code: str | None = None
    pop_ea_code: str
    ea_name: str | None = None
    visit_date: date
    phase: str
    visit_type: str | None = None
    team_found: bool | None = None
    overall_rating: int | None = None
    critical_count: int
    open_issues: int
    flags: list[str]
    distance_to_ea_m: float | None = None
    lat: float
    lng: float
    status: str
    server_updated_at: datetime


class VisitDetail(VisitRow):
    answers: dict
    indicators: dict
    issues: list[IssueOut]
    accuracy_m: float | None = None
    gps_at: datetime | None = None
    review_note: str | None = None
    reviewed_at: datetime | None = None
    client_created_at: datetime
