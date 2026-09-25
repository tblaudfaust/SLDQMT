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
    active: bool


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
