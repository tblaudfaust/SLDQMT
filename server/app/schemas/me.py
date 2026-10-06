from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


# ---- evaluations (M&E staff) --------------------------------------------------


class EvaluationIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    training_mode: str = Field(pattern="^(ONLINE|IN_PERSON)$")
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = Field(default=None, max_length=2000)


class EvaluationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    training_mode: str | None = Field(default=None, pattern="^(ONLINE|IN_PERSON)$")
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, pattern="^(OPEN|CLOSED)$")


class EvaluationOut(ORMModel):
    id: int
    title: str
    training_mode: str
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = None
    token: str
    status: str
    created_at: datetime
    registered: int = 0
    submitted: int = 0
    trainees: int = 0
    trainers: int = 0


class RespondentOut(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    registered_at: datetime
    role: str | None = None  # from the response, once submitted
    submitted_at: datetime | None = None
    response_id: int | None = None
    district: str | None = None


class ItemStat(BaseModel):
    code: str
    text: str
    n: int  # valid 1..5 ratings
    na: int
    mean: float | None = None
    pct_favourable: float | None = None  # ratings 4 or 5
    flag: bool = False


class DomainStat(BaseModel):
    code: str
    label: str
    n_respondents: int
    mean: float | None = None
    pct_favourable: float | None = None
    flag: bool = False
    threshold: int
    items: list[ItemStat]


class Breakdown(BaseModel):
    label: str
    count: int
    pct: float


class OpenAnswer(BaseModel):
    code: str
    text: str
    role: str
    district: str | None = None


class Results(BaseModel):
    evaluation: EvaluationOut
    registered: int
    submitted: int
    trainees: int
    trainers: int
    neither: int
    response_rate: float | None = None  # submitted / registered
    profile: dict[str, list[Breakdown]]  # district, role, institution, sex, age
    completion: dict[str, list[Breakdown]]  # A06, A07, A08, B07
    domains: list[DomainStat]
    knowledge: dict[str, float | None]  # before, after, gain, pct_positive
    overall: dict[str, list[Breakdown]]  # H03, H04, H05, H06, H07, J10, J11
    reinforcement: dict[str, list[Breakdown]]  # H08 (trainees), J13 (trainers)
    strengths: list[ItemStat]
    weaknesses: list[ItemStat]
    open_feedback: list[OpenAnswer]


# ---- public evaluation page ---------------------------------------------------


class PublicEvaluation(BaseModel):
    title: str
    training_mode: str
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = None
    status: str
    form: dict[str, Any]


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=200)
    phone: str = Field(min_length=8, max_length=32)


class RegisterOut(BaseModel):
    respondent_id: int
    resume_token: str
    full_name: str
    already_submitted: bool


class SubmitIn(BaseModel):
    respondent_id: int
    resume_token: str
    answers: dict[str, Any]


class SubmitOut(BaseModel):
    response_id: int
    role: str
    submitted_at: datetime
