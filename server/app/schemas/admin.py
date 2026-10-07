from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.device import DeviceStatus
from app.models.user import Role
from app.schemas.auth import ScopeOut
from app.schemas.reference import CreatedAccount
from app.schemas.common import ORMModel


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    full_name: str = Field(min_length=1, max_length=160)
    phone: str | None = None
    role: Role
    staff_code: str | None = Field(default=None, max_length=32)
    active_from: date | None = None
    active_until: date | None = None
    district_ids: list[int] = []
    region_ids: list[int] = []


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    role: Role | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=256)
    staff_code: str | None = Field(default=None, max_length=32)  # "" clears it
    active_from: date | None = None
    active_until: date | None = None
    district_ids: list[int] | None = None
    region_ids: list[int] | None = None


class UserAdminOut(ORMModel):
    id: int
    username: str
    full_name: str
    phone: str | None = None
    role: Role
    active: bool
    staff_code: str | None = None
    active_from: date | None = None
    active_until: date | None = None
    must_change_password: bool | None = None
    last_login_at: datetime | None = None
    pin_reset_requested_at: datetime | None = None
    scopes: list[ScopeOut] = []


class UserStats(BaseModel):
    total: int
    active: int
    inactive: int
    by_role: dict[str, int]
    locked: int
    never_logged_in: int


class UserActivity(BaseModel):
    user: UserAdminOut
    devices: list["DeviceOut"]
    recent: list["AuditOut"]
    counts: dict[str, int]


class PasswordResetIn(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=256)
    """Leave empty to have a temporary password generated and returned once."""


class PasswordResetOut(BaseModel):
    user_id: int
    username: str
    temporary_password: str | None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=256)


class OfficerPairIn(BaseModel):
    """A linked Field Monitor + DQM pair of one district: FM-Bo-048 and DQM-Bo-048 (next free number when omitted)."""

    district_id: int
    number: int | None = Field(default=None, ge=1, le=9999)
    fm_full_name: str | None = Field(default=None, max_length=160)
    dqm_full_name: str | None = Field(default=None, max_length=160)
    fm_phone: str | None = Field(default=None, max_length=32)
    dqm_phone: str | None = Field(default=None, max_length=32)
    fm_password: str | None = Field(default=None, min_length=8, max_length=256)
    dqm_password: str | None = Field(default=None, min_length=8, max_length=256)


class OfficerPairOut(BaseModel):
    field_monitor: CreatedAccount
    dqm: CreatedAccount
    sa_count: int  # SAs already carrying this pair's codes (0 = assign them on the Workload page)


class UserImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[str]
    created_users: list[str]


class DeviceOut(ORMModel):
    id: str
    user_id: int
    username: str | None = None
    full_name: str | None = None
    model: str | None = None
    android_version: str | None = None
    app_version: str | None = None
    status: DeviceStatus
    registered_at: datetime
    last_login_at: datetime | None = None
    last_sync_at: datetime | None = None
    pending_reported: int


class DeviceStatusUpdate(BaseModel):
    status: DeviceStatus


class SettingsUpdate(BaseModel):
    follow_up_interval_hours: float | None = Field(default=None, gt=0, le=72)
    quiet_hours_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    quiet_hours_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    offline_days: int | None = Field(default=None, ge=1, le=90)
    # M&E field monitoring GPS checks and phase dates
    mefm_ea_distance_m: int | None = Field(default=None, ge=50, le=50000)
    mefm_gps_accuracy_m: int | None = Field(default=None, ge=5, le=1000)
    mefm_max_speed_kmh: int | None = Field(default=None, ge=10, le=500)
    mefm_night_start: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    mefm_night_end: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    mefm_phase_listing_start: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    mefm_phase_enumeration_start: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    mefm_phase_mopup_start: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2}-\d{2})?$")
    mefm_phase_end: str | None = Field(default=None, pattern=r"^(\d{4}-\d{2}-\d{2})?$")


class ImportResult(BaseModel):
    regions: int
    districts: int
    teams: int
    supervisors: int
    enumerators: int
    eas: int
    chiefdoms: int = 0
    sections: int = 0
    assigned: int = 0  # SAs that received a Field Monitor / DQM assignment
    updated: int = 0  # names or attributes changed on rows that already existed
    dry_run: bool = False  # nothing was saved; the counts show what applying the file would do
    removed: dict = {}  # SAs and EAs in the touched districts that the file no longer lists (kept, reported)
    rows: int
    warnings: list[str]


class FrameVersionOut(BaseModel):
    id: int
    filename: str
    applied_by: str | None = None
    applied_at: datetime
    rows: int
    counts: dict
    changes: dict


class AuditOut(ORMModel):
    id: int
    at: datetime
    user_id: int | None
    user_name: str | None = None
    username: str | None = None
    action: str
    entity: str | None
    entity_id: str | None
    detail: str | None
    ip: str | None = None


class PermissionInfo(BaseModel):
    code: str
    group: str
    description: str


class RoleMatrix(BaseModel):
    roles: dict[str, list[str]]
    defaults: dict[str, list[str]]
    permissions: list[PermissionInfo]


class RolePermissionsIn(BaseModel):
    codes: list[str]


class UserPermissionsOut(BaseModel):
    user_id: int
    role: Role
    role_codes: list[str]
    grant: list[str]
    revoke: list[str]
    effective: list[str]


class UserPermissionsIn(BaseModel):
    grant: list[str] = []
    revoke: list[str] = []


class PinResetOut(BaseModel):
    user_id: int
    username: str
    pin_reset_requested_at: datetime
