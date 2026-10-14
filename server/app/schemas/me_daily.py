"""Daily Evaluation: rounds with their agenda, the Daily Facilitator Report and the summary the dashboard shows."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AgendaItemIn(BaseModel):
    day: int = Field(ge=1, le=60)
    topic: str = Field(min_length=1, max_length=200)
    planned_start: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    planned_end: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    details: str | None = Field(default=None, max_length=4000)
    responsible: str | None = Field(default=None, max_length=200)


class AgendaItemOut(AgendaItemIn):
    id: int
    position: int


class RoundIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    phase: str = Field(pattern="^(MASTER|TOT|FIELD)$")
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = Field(default=None, max_length=2000)
    agenda_template: str | None = None  # a bundled agenda to load at creation, e.g. MASTER_10_DAYS


class AgendaTemplate(BaseModel):
    key: str
    title: str
    phase: str
    source: str | None = None
    days: int
    day_titles: dict[str, str] = {}
    items: list[AgendaItemIn]


class AgendaParseOut(BaseModel):
    items: list[AgendaItemIn]
    days: int
    day_titles: dict[str, str] = {}
    warnings: list[str] = []


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
    reports: int = 0
    classes: int = 0
    days: int = 0
    last_report_date: date | None = None
    overall_mean: float | None = None
    delivered_pct: float | None = None
    open_escalations: int = 0
    low_scores: int = 0  # reports with any criterion scored 1 or 2


class SessionRow(BaseModel):
    topic: str = Field(max_length=200)
    planned_start: str | None = None
    planned_end: str | None = None
    actual_start: str | None = None
    actual_end: str | None = None
    delivered: str | None = None  # Y | P | N
    reason: str | None = Field(default=None, max_length=500)
    delta: int | None = None  # minutes over (+) / under (−), computed by the server


class MaterialIssue(BaseModel):
    item: str = Field(max_length=300)
    type: str | None = None  # ERROR | MISMATCH | UNCLEAR | MISSING
    severity: str | None = None  # H | M | L
    correction: str | None = Field(default=None, max_length=1000)


class Escalation(BaseModel):
    issue: str = Field(max_length=1000)
    raised_to: str | None = Field(default=None, max_length=160)
    owner: str | None = Field(default=None, max_length=160)
    needed_by: str | None = Field(default=None, max_length=40)
    status: str | None = "OPEN"  # OPEN | IN_PROGRESS | RESOLVED


class ReportIn(BaseModel):
    """The Daily Facilitator Report as sent from the public page or edited on the dashboard."""

    phase: str = Field(pattern="^(MASTER|TOT|FIELD)$")
    platform_venue: str = Field(min_length=1, max_length=160)
    class_hall: str = Field(min_length=1, max_length=80)
    training_day: int = Field(ge=1, le=60)
    report_date: date
    lead_facilitator: str = Field(min_length=2, max_length=160)
    co_facilitators: str | None = Field(default=None, max_length=300)
    district: str | None = Field(default=None, max_length=60)
    sessions: list[SessionRow] = []
    carried_over: list[str] = []
    quiz_administered: bool | None = None
    quiz_title: str | None = Field(default=None, max_length=200)
    mean_score: float | None = Field(default=None, ge=0, le=100)
    pass_rate: float | None = Field(default=None, ge=0, le=100)
    quiz_comments: str | None = Field(default=None, max_length=1000)
    practice_minutes: int | None = Field(default=None, ge=0, le=1440)
    practice_comments: str | None = Field(default=None, max_length=1000)
    hardest_topics: list[str] = []
    hardest_comments: str | None = Field(default=None, max_length=1000)
    q_content: int | None = Field(default=None, ge=1, le=5)
    q_content_evidence: str | None = Field(default=None, max_length=1000)
    q_engagement: int | None = Field(default=None, ge=1, le=5)
    q_engagement_evidence: str | None = Field(default=None, max_length=1000)
    q_time: int | None = Field(default=None, ge=1, le=5)
    q_time_evidence: str | None = Field(default=None, max_length=1000)
    q_illustrations: int | None = Field(default=None, ge=1, le=5)
    q_illustrations_evidence: str | None = Field(default=None, max_length=1000)
    material_issues: list[MaterialIssue] = []
    g_internet: int | None = Field(default=None, ge=1, le=5)
    g_internet_details: str | None = Field(default=None, max_length=1000)
    g_power: int | None = Field(default=None, ge=1, le=5)
    g_power_details: str | None = Field(default=None, max_length=1000)
    g_devices: int | None = Field(default=None, ge=0, le=5000)
    g_devices_details: str | None = Field(default=None, max_length=1000)
    g_food: int | None = Field(default=None, ge=1, le=5)
    g_food_details: str | None = Field(default=None, max_length=1000)
    escalations: list[Escalation] = []


class PublicSubmitIn(ReportIn):
    edit_token: str | None = None
    report_id: int | None = None


class PublicSubmitOut(BaseModel):
    report_id: int
    edit_token: str
    submitted_at: datetime
    overall: float


class ReportOut(BaseModel):
    """Every field of one report, with labels and computed figures."""

    id: int
    round_id: int
    phase: str
    phase_label: str
    platform_venue: str
    class_hall: str
    training_day: int
    report_date: date
    lead_facilitator: str
    co_facilitators: str | None = None
    district: str | None = None
    sessions: list[SessionRow]
    sessions_planned: int
    sessions_delivered: int  # Y
    sessions_partly: int
    sessions_not: int
    minutes_delta: int | None = None  # sum of the session deltas
    carried_over: list[str]
    quiz_administered: bool
    quiz_title: str | None = None
    mean_score: float | None = None
    pass_rate: float | None = None
    quiz_comments: str | None = None
    practice_minutes: int | None = None
    practice_comments: str | None = None
    hardest_topics: list[str]
    hardest_comments: str | None = None
    q_content: int
    q_content_evidence: str | None = None
    q_engagement: int
    q_engagement_evidence: str | None = None
    q_time: int
    q_time_evidence: str | None = None
    q_illustrations: int
    q_illustrations_evidence: str | None = None
    overall: float
    low_scores: int  # criteria scored 1 or 2
    material_issues: list[MaterialIssue]
    g_internet: int
    g_internet_details: str | None = None
    g_power: int
    g_power_details: str | None = None
    g_devices: int
    g_devices_details: str | None = None
    g_food: int
    g_food_details: str | None = None
    escalations: list[Escalation]
    open_escalations: int
    submitted_at: datetime
    updated_at: datetime
    edited_by_name: str | None = None


class CountRow(BaseModel):
    code: str
    label: str
    count: int
    pct: float


class GroupRow(BaseModel):
    """Coverage, learning, quality and logistics for one day, class, district, facilitator or phase."""

    key: str
    label: str
    reports: int
    sessions: int
    delivered: int
    partly: int
    not_delivered: int
    delivered_pct: float | None = None
    minutes_delta: int
    carried_over: int
    quizzes: int
    mean_score: float | None = None
    pass_rate: float | None = None
    practice_minutes_avg: float | None = None
    q_content: float | None = None
    q_engagement: float | None = None
    q_time: float | None = None
    q_illustrations: float | None = None
    overall: float | None = None
    low_scores: int
    material_issues: int
    high_severity: int
    internet: float | None = None
    power: float | None = None
    devices_short: int
    food: float | None = None
    escalations: int
    open_escalations: int


class TopicRow(BaseModel):
    """One agenda topic across every report: how often it was delivered, carried over or found hardest."""

    topic: str
    day: int | None = None
    planned: int
    delivered: int
    partly: int
    not_delivered: int
    minutes_delta: int
    carried_over: int
    hardest: int


class LogRow(BaseModel):
    report_id: int
    report_date: date
    training_day: int
    class_hall: str
    district: str | None = None
    lead_facilitator: str
    fields: dict[str, str | None]


class Summary(BaseModel):
    round: RoundOut
    filters: dict[str, str | None]
    reports: int
    classes: int
    days: int
    facilitators: int
    districts: int
    sessions: int
    delivered: int
    partly: int
    not_delivered: int
    delivered_pct: float | None = None
    minutes_delta: int
    carried_over: int
    quizzes: int
    mean_score: float | None = None
    pass_rate: float | None = None
    practice_minutes_avg: float | None = None
    practice_na: int
    quality: dict[str, float | None]  # content / engagement / time / illustrations / overall means
    quality_distribution: dict[str, list[CountRow]]  # per criterion, scores 5..1
    overall_distribution: list[CountRow]  # overall rounded 5..1
    low_scores: int  # reports with any criterion at 1 or 2
    material_issues: int
    issues_by_type: list[CountRow]
    issues_by_severity: list[CountRow]
    logistics: dict[str, float | None]  # internet / power / food means
    devices_short: int
    escalations: int
    open_escalations: int
    escalations_by_status: list[CountRow]
    by_day: list[GroupRow]
    by_class: list[GroupRow]
    by_district: list[GroupRow]
    by_facilitator: list[GroupRow]
    by_phase: list[GroupRow]
    topics: list[TopicRow]
    hardest_topics: list[CountRow]
    issues_log: list[LogRow]
    escalations_log: list[LogRow]
    evidence_log: list[LogRow]  # scores of 1, 2 or 5 with their evidence
    carried_over_log: list[LogRow]
    latest: list[ReportOut]


class EscalationStatusIn(BaseModel):
    index: int = Field(ge=0, le=20)
    status: str = Field(pattern="^(OPEN|IN_PROGRESS|RESOLVED)$")


class PublicRound(BaseModel):
    title: str
    phase: str
    period_start: date | None = None
    period_end: date | None = None
    description: str | None = None
    status: str
    agenda: list[AgendaItemOut]
    form: dict
