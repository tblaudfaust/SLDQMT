"""M&E Field Tool: the KPI report, the offline sync envelope, the geography bundle and the dashboard summary."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportIn(BaseModel):
    client_id: str = Field(min_length=8, max_length=48)
    phase: str = Field(pattern="^(MT|TOT|TOE|L|E)$")
    report_date: date
    week: int | None = Field(default=None, ge=1, le=60)
    district_id: int | None = None
    chiefdom: str | None = Field(default=None, max_length=160)
    section: str | None = Field(default=None, max_length=160)
    team_id: int | None = None
    sa_code: str | None = Field(default=None, max_length=32)
    ea_codes: list[str] = Field(default_factory=list, max_length=60)
    practice_team: str | None = Field(default=None, max_length=120)
    respondent_name: str | None = Field(default=None, max_length=160)
    respondent_role: str | None = Field(default=None, max_length=24)
    collection_mode: str | None = Field(default=None, pattern="^(IN_PERSON|REMOTE)$")
    eas_urban: int | None = Field(default=None, ge=0, le=1000)
    eas_rural: int | None = Field(default=None, ge=0, le=1000)
    enumerators: int | None = Field(default=None, ge=0, le=1000)
    capi_version: str | None = Field(default=None, max_length=40)
    lat: float | None = None
    lng: float | None = None
    answers: dict[str, Any] = Field(default_factory=dict)
    submitted_at: datetime | None = None  # when the device saved it (offline); the server time otherwise
    device: str | None = Field(default=None, max_length=160)


class SyncIn(BaseModel):
    reports: list[ReportIn] = Field(max_length=200)


class SyncResult(BaseModel):
    client_id: str
    id: int | None = None
    status: str  # created | updated | error
    message: str | None = None


class SyncOut(BaseModel):
    results: list[SyncResult]
    created: int = 0
    updated: int = 0
    errors: int = 0


class ReportOut(BaseModel):
    id: int
    client_id: str
    phase: str
    phase_label: str
    report_date: date
    week: int | None = None
    district_id: int | None = None
    district: str | None = None
    region: str | None = None
    chiefdom: str | None = None
    section: str | None = None
    team_id: int | None = None
    sa_code: str | None = None
    sa_name: str | None = None
    ea_codes: list[str] = []
    practice_team: str | None = None
    respondent_name: str | None = None
    respondent_role: str | None = None
    respondent_role_label: str | None = None
    collection_mode: str | None = None
    collection_mode_label: str | None = None
    eas_urban: int | None = None
    eas_rural: int | None = None
    enumerators: int | None = None
    capi_version: str | None = None
    lat: float | None = None
    lng: float | None = None
    answers: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    officer: str | None = None
    user_id: int
    submitted_at: datetime
    updated_at: datetime | None = None
    edited_by_name: str | None = None


class GeoDistrict(BaseModel):
    id: int
    code: str
    name: str
    region: str


class GeoChiefdom(BaseModel):
    id: int
    district_id: int
    code: str
    name: str


class GeoSection(BaseModel):
    id: int
    district_id: int
    chiefdom_id: int
    code: str
    name: str


class GeoTeam(BaseModel):
    id: int
    district_id: int
    code: str
    name: str
    chiefdom: str | None = None
    supervisor: str | None = None
    enumerators: int = 0
    eas: int = 0
    eas_urban: int = 0
    eas_rural: int = 0
    expected_households: int | None = None


class GeoEa(BaseModel):
    team_id: int
    code: str
    name: str | None = None
    locality: str | None = None
    urban: bool | None = None
    households: int | None = None


class GeoBundle(BaseModel):
    version: str
    generated_at: datetime
    districts: list[GeoDistrict]
    chiefdoms: list[GeoChiefdom]
    sections: list[GeoSection]
    teams: list[GeoTeam]
    eas: list[GeoEa] = []  # the EAs of every SA when the scope is a district or a region; otherwise fetched per SA
    eas_on_demand: bool = False


class FieldAccountIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    full_name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    role: str = Field(pattern="^(ME_DISTRICT|ME_REGIONAL)$")
    district_ids: list[int] = Field(default_factory=list, max_length=20)
    region_ids: list[int] = Field(default_factory=list, max_length=5)
    password: str | None = Field(default=None, min_length=8, max_length=256)  # generated when absent


class FieldAccountUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    active: bool | None = None
    district_ids: list[int] | None = Field(default=None, max_length=20)
    region_ids: list[int] | None = Field(default=None, max_length=5)


class FieldAccountOut(BaseModel):
    id: int
    username: str
    full_name: str
    phone: str | None = None
    role: str
    role_label: str
    active: bool
    districts: list[str] = []
    district_ids: list[int] = []
    regions: list[str] = []
    region_ids: list[int] = []
    must_change_password: bool = False
    last_login_at: datetime | None = None
    reports: int = 0
    temporary_password: str | None = None  # only on creation or reset


class FieldAccountOptions(BaseModel):
    districts: list[GeoDistrict]
    regions: list[dict]


class CountRow(BaseModel):
    code: str
    label: str
    count: int
    pct: float | None = None


class GroupRow(BaseModel):
    key: str
    label: str
    reports: int = 0
    sas: int = 0
    officers: int = 0
    coverage_pct: float | None = None
    synced_pct: float | None = None
    error_pct: float | None = None
    tablets_pct: float | None = None
    informed_pct: float | None = None
    support_pct: float | None = None
    on_schedule_pct: float | None = None
    overall: float | None = None
    safety_concerns: int = 0
    escalations: int = 0


class Attention(BaseModel):
    report_id: int
    report_date: date
    phase: str
    district: str | None = None
    sa: str | None = None
    officer: str | None = None
    reasons: list[str]


class Summary(BaseModel):
    scope: str
    reports: int = 0
    sas: int = 0
    districts: int = 0
    officers: int = 0
    last_date: date | None = None
    coverage_pct: float | None = None
    synced_pct: float | None = None
    error_pct: float | None = None
    tablets_pct: float | None = None
    reinterview_pct: float | None = None
    informed_pct: float | None = None
    aware_pct: float | None = None
    trust_pct: float | None = None
    support_pct: float | None = None
    channel_pct: float | None = None
    on_schedule_pct: float | None = None
    overall: float | None = None
    safety_concerns: int = 0
    escalations: int = 0
    follow_ups: int = 0
    by_phase: list[GroupRow] = []
    by_district: list[GroupRow] = []
    by_week: list[GroupRow] = []
    by_officer: list[GroupRow] = []
    channels: list[CountRow] = []
    blockers: list[CountRow] = []
    error_types: list[CountRow] = []
    risks: list[CountRow] = []
    overall_counts: list[CountRow] = []
    attention: list[Attention] = []
    latest: list[ReportOut] = []
