"""Daily Facilitator's Report: the report, the public submission, the summary by venue, hall and day."""

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel
from app.schemas.me_fac import AgendaItemOut, RoundOut


class ReportIn(BaseModel):
    report_date: date
    training_day: int = Field(ge=1, le=60)
    venue: str = Field(min_length=2, max_length=80)
    hall: str = Field(min_length=1, max_length=80)
    lead_facilitator: str = Field(min_length=2, max_length=160)
    other_facilitators: str | None = Field(default=None, max_length=2000)
    email: str | None = Field(default=None, max_length=160, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=32)
    registered: int = Field(ge=0, le=1000)
    present: int = Field(ge=0, le=1000)
    delivered: str = Field(pattern="^(FULL|PARTLY|NO)$")
    missed_sessions: list[str] = Field(default_factory=list, max_length=40)
    minutes_lost: int | None = Field(default=None, ge=0, le=1440)
    missed_reason: str | None = Field(default=None, max_length=4000)
    r_knowledge: int = Field(ge=1, le=5)
    r_engagement: int = Field(ge=1, le=5)
    r_illustrations: int = Field(ge=1, le=5)
    r_connectivity: int = Field(ge=1, le=5)
    r_coordination: int = Field(ge=1, le=5)
    e_internet: int | None = Field(default=None, ge=1, le=5)
    e_internet_details: str | None = Field(default=None, max_length=2000)
    e_power: int | None = Field(default=None, ge=1, le=5)
    e_power_details: str | None = Field(default=None, max_length=2000)
    e_devices: str | None = Field(default=None, max_length=200)
    e_devices_details: str | None = Field(default=None, max_length=2000)
    e_food: str | None = Field(default=None, max_length=200)
    e_food_details: str | None = Field(default=None, max_length=2000)
    went_right: str = Field(min_length=3, max_length=4000)
    repeat_share: str | None = Field(default=None, max_length=4000)
    went_wrong: str = Field(min_length=3, max_length=4000)
    difficult_topics: list[str] = Field(default_factory=list, max_length=40)
    difficult_notes: str | None = Field(default=None, max_length=4000)
    recommendations: str = Field(min_length=3, max_length=4000)
    gaps: str = Field(min_length=3, max_length=4000)
    actors: list[str] = Field(default_factory=list, max_length=8)
    actor_other: str | None = Field(default=None, max_length=160)
    comments: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def _rules(self):
        if self.present > self.registered:
            raise ValueError("Participants present cannot exceed the participants registered")
        if self.delivered in ("PARTLY", "NO") and not (self.missed_reason and self.missed_reason.strip()):
            raise ValueError("Say which sessions were affected, how many minutes were lost and why")
        if not self.actors:
            raise ValueError("Choose who should act")
        if "OTHER" in self.actors and not (self.actor_other and self.actor_other.strip()):
            raise ValueError("Specify who else should act")
        return self


class PublicSubmitIn(ReportIn):
    report_id: int | None = None  # with edit_token: correct a report sent from the same device
    edit_token: str | None = None


class PublicSubmitOut(BaseModel):
    report_id: int
    edit_token: str
    submitted_at: datetime
    mean_rating: float
    attendance_pct: float | None = None


class ReportOut(ORMModel):
    id: int
    round_id: int
    report_date: date
    training_day: int
    venue: str
    hall: str
    lead_facilitator: str
    other_facilitators: str | None = None
    email: str | None = None
    phone: str | None = None
    registered: int
    present: int
    attendance_pct: float | None = None
    delivered: str
    delivered_label: str = ""
    missed_sessions: list[str] = []
    minutes_lost: int | None = None
    missed_reason: str | None = None
    r_knowledge: int
    r_engagement: int
    r_illustrations: int
    r_connectivity: int
    r_coordination: int
    mean_rating: float
    e_internet: int | None = None
    e_internet_details: str | None = None
    e_power: int | None = None
    e_power_details: str | None = None
    e_devices: str | None = None
    e_devices_details: str | None = None
    e_food: str | None = None
    e_food_details: str | None = None
    went_right: str
    repeat_share: str | None = None
    went_wrong: str
    difficult_topics: list[str] = []
    difficult_notes: str | None = None
    recommendations: str
    gaps: str
    actors: list[str] = []
    actor_labels: list[str] = []
    actor_other: str | None = None
    comments: str | None = None
    submitted_at: datetime
    edited_by_name: str | None = None
    reasons: list[str] = []  # why it needs attention (empty = fine)


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
    venue: str | None = None
    hall: str | None = None
    reports: int = 0
    halls: int = 0
    days: int = 0
    registered: int = 0
    present: int = 0
    attendance_pct: float | None = None
    mean_rating: float | None = None
    ratings: dict[str, float | None] = {}
    delivered_full_pct: float | None = None
    minutes_lost: int = 0
    internet: float | None = None
    power: float | None = None
    low_ratings: int = 0  # reports with a rating of 1 or 2
    attention: int = 0


class RoundRow(BaseModel):
    round: RoundOut
    reports: int = 0
    halls: int = 0
    venues: int = 0
    days: int = 0
    last_date: date | None = None
    mean_rating: float | None = None
    attendance_pct: float | None = None
    attention: int = 0
    report_url: str | None = None


class Summary(BaseModel):
    round: RoundOut
    report_url: str | None = None
    reports: int = 0
    halls: int = 0
    venues: int = 0
    days: int = 0
    facilitators: int = 0
    registered: int = 0
    present: int = 0
    attendance_pct: float | None = None
    mean_rating: float | None = None
    delivered: list[CountRow] = []
    minutes_lost: int = 0
    internet: float | None = None
    power: float | None = None
    criteria: list[CriterionRow] = []
    low_ratings: int = 0
    attention: int = 0
    by_venue: list[GroupRow] = []
    by_hall: list[GroupRow] = []
    by_day: list[GroupRow] = []
    actors: list[CountRow] = []
    difficult_topics: list[CountRow] = []
    missed_sessions: list[CountRow] = []
    needs_attention: list[ReportOut] = []
    latest: list[ReportOut] = []


class PublicRound(BaseModel):
    title: str
    phase: str
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = None
    status: str
    agenda: list[AgendaItemOut] = []
    form: dict
