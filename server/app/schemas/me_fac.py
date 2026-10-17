"""Facilitator assessment: trainings with the chapters per day, the daily trainer rating and the summary by district, hall, day and trainer."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AgendaItemIn(BaseModel):
    day: int = Field(ge=1, le=60)
    topic: str = Field(min_length=1, max_length=200)
    details: str | None = Field(default=None, max_length=4000)


class AgendaItemOut(AgendaItemIn):
    id: int
    position: int


class RoundIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    phase: str = Field(pattern="^(MASTER|TOT|FIELD)$")
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = Field(default=None, max_length=2000)
    agenda_template: str | None = None  # a bundled agenda to load at creation, e.g. TRAINING_2026


class RoundUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    phase: str | None = Field(default=None, pattern="^(MASTER|TOT|FIELD)$")
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, pattern="^(OPEN|CLOSED)$")


class RoundOut(ORMModel):
    id: int
    title: str
    phase: str
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = None
    token: str
    status: str
    created_at: datetime
    share_url: str | None = None
    agenda_days: int = 0
    agenda_items: int = 0
    assessments: int = 0
    trainers: int = 0
    halls: int = 0
    districts: int = 0
    days: int = 0
    last_date: date | None = None
    mean_pct: float | None = None
    needs_improvement: int = 0  # assessments in the lowest band


class SectionRating(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    rating: int | None = Field(default=None, ge=1, le=4)


class AssessmentIn(BaseModel):
    assessment_date: date
    training_day: int = Field(ge=1, le=60)
    district: str | None = Field(default=None, max_length=60)
    hall: str = Field(min_length=1, max_length=80)
    monitor_name: str = Field(min_length=2, max_length=160)
    trainer_name: str = Field(min_length=2, max_length=160)
    s_technical: int = Field(ge=1, le=4)
    s_clarity: int = Field(ge=1, le=4)
    s_practical: int = Field(ge=1, le=4)
    s_participation: int = Field(ge=1, le=4)
    s_time: int = Field(ge=1, le=4)
    sections: list[SectionRating] = Field(default_factory=list, max_length=40)
    strengths: str | None = Field(default=None, max_length=2000)
    improvements: str | None = Field(default=None, max_length=2000)
    comments: str | None = Field(default=None, max_length=2000)


class PublicSubmitIn(AssessmentIn):
    assessment_id: int | None = None  # with edit_token: correct a rating sent from the same device
    edit_token: str | None = None


class PublicSubmitOut(BaseModel):
    assessment_id: int
    edit_token: str
    submitted_at: datetime
    section_a_total: int
    score_pct: float
    band: str
    band_label: str


class AssessmentOut(ORMModel):
    id: int
    round_id: int
    assessment_date: date
    training_day: int
    district: str | None = None
    hall: str
    monitor_name: str
    trainer_name: str
    s_technical: int
    s_clarity: int
    s_practical: int
    s_participation: int
    s_time: int
    section_a_total: int
    section_a_band: str
    sections: list[SectionRating] = []
    section_b_total: int
    section_b_max: int
    score_pct: float
    band: str
    band_label: str
    strengths: str | None = None
    improvements: str | None = None
    comments: str | None = None
    submitted_at: datetime
    edited_by_name: str | None = None
    lowest: int  # the lowest section A score


class CountRow(BaseModel):
    code: str
    label: str
    count: int
    pct: float | None = None


class CriterionRow(BaseModel):
    key: str
    label: str
    mean: float | None = None
    distribution: list[CountRow] = []


class GroupRow(BaseModel):
    key: str
    label: str
    district: str | None = None
    hall: str | None = None
    assessments: int = 0
    trainers: int = 0
    halls: int = 0
    monitors: int = 0
    mean_a_total: float | None = None
    mean_pct: float | None = None
    band: str | None = None
    band_label: str | None = None
    criteria: dict[str, float | None] = {}
    bands: dict[str, int] = {}
    lowest_criterion: str | None = None
    low_scores: int = 0  # ratings with a criterion at 1 or 2


class TopicRow(BaseModel):
    day: int
    topic: str
    ratings: int = 0
    mean: float | None = None


class Summary(BaseModel):
    round: RoundOut
    assessments: int = 0
    trainers: int = 0
    halls: int = 0
    districts: int = 0
    monitors: int = 0
    days: int = 0
    mean_a_total: float | None = None
    mean_pct: float | None = None
    band_counts: list[CountRow] = []
    criteria: list[CriterionRow] = []
    low_scores: int = 0
    by_district: list[GroupRow] = []
    by_hall: list[GroupRow] = []  # district · hall
    by_day: list[GroupRow] = []
    by_trainer: list[GroupRow] = []
    by_monitor: list[GroupRow] = []
    topics: list[TopicRow] = []
    needs_attention: list[GroupRow] = []  # trainers in the lowest two bands or with a criterion at 1 or 2
    latest: list[AssessmentOut] = []


class PublicRound(BaseModel):
    title: str
    phase: str
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = None
    status: str
    agenda: list[AgendaItemOut] = []
    form: dict
