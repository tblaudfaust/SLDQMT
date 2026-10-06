from pydantic import BaseModel

from app.schemas.common import ORMModel


class RegionOut(ORMModel):
    id: int
    code: str
    name: str


class DistrictOut(ORMModel):
    id: int
    region_id: int
    code: str
    name: str


class TeamOut(ORMModel):
    id: int
    district_id: int
    code: str
    name: str
    chiefdom: str | None = None
    local_council: str | None = None
    ea_count: int | None = None
    monitor_code: str | None = None
    dqm_code: str | None = None
    active: bool


class WorkloadRow(BaseModel):
    """One SA with the officers responsible for it (and their accounts, when created)."""

    team_id: int
    district_id: int
    district: str
    code: str
    name: str
    chiefdom: str | None = None
    ea_count: int | None = None
    monitor_code: str | None = None
    monitor_name: str | None = None
    dqm_code: str | None = None
    dqm_name: str | None = None


class OfficerOut(BaseModel):
    """A Field Monitor or DQM officer of a district, by staff code (with the account when it exists)."""

    staff_code: str
    role: str  # FIELD_MONITOR or DISTRICT_DQM
    district_id: int
    full_name: str | None = None
    user_id: int | None = None
    sa_count: int = 0


class CreatedAccount(BaseModel):
    username: str
    staff_code: str
    role: str
    district: str
    password: str  # shown once, in the response that created it


class WorkloadAccountsOut(BaseModel):
    created: list[CreatedAccount]
    existing: int  # officers of the workload that already had an account


class WorkloadAssignIn(BaseModel):
    """Give the listed SAs to another officer. None keeps the current officer; "" clears it."""

    team_ids: list[int]
    monitor_code: str | None = None
    dqm_code: str | None = None


class SupervisorOut(ORMModel):
    id: int
    team_id: int
    code: str | None = None
    name: str
    phone: str | None = None
    active: bool


class EnumeratorOut(ORMModel):
    id: int
    team_id: int
    code: str | None = None
    name: str
    phone: str | None = None
    active: bool


class EAOut(ORMModel):
    id: int
    team_id: int
    code: str
    name: str | None = None
    locality: str | None = None
    households: int | None = None
    lat: float | None = None
    lng: float | None = None
    active: bool


class PickListOut(ORMModel):
    id: int
    code: str
    name: str
    active: bool
    sort_order: int


class ReferenceBundle(BaseModel):
    version: str
    regions: list[RegionOut]
    districts: list[DistrictOut]
    teams: list[TeamOut]
    supervisors: list[SupervisorOut]
    enumerators: list[EnumeratorOut]
    eas: list[EAOut]
    categories: list[PickListOut]
    sources: list[PickListOut]
    settings: dict[str, str]


class PickListIn(BaseModel):
    code: str
    name: str
    active: bool = True
    sort_order: int = 0
