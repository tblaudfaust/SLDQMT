from datetime import datetime

from pydantic import BaseModel, Field

from app.models.user import Role
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    device_id: str | None = Field(default=None, max_length=36)


class RefreshRequest(BaseModel):
    refresh_token: str


class ScopeOut(ORMModel):
    region_id: int | None = None
    district_id: int | None = None


class UserOut(ORMModel):
    id: int
    username: str
    full_name: str
    phone: str | None = None
    role: Role
    active: bool
    last_login_at: datetime | None = None
    staff_code: str | None = None
    assigned_sas: int = 0  # SAs in this officer's workload (0 = none assigned, district scope applies)
    district_ids: list[int] | None = None
    scopes: list[ScopeOut] = []
    permissions: list[str] = []


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    settings: dict[str, str]
