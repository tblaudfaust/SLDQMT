"""Daily Evaluation: the Daily Facilitator Report, one per class per day, grouped in rounds (a training)
that carry the agenda (sessions per day) and are shared with lead facilitators through a link."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class MeDailyRound(TimestampMixin, Base):
    """A training whose classes report daily (e.g. 'Field staff training, Southern region')."""

    __tablename__ = "me_daily_round"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)  # MASTER | TOT | FIELD
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    token: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False)  # OPEN | CLOSED
    created_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))

    agenda: Mapped[list["MeDailyAgendaItem"]] = relationship(back_populates="round", cascade="all, delete-orphan", order_by="MeDailyAgendaItem.day, MeDailyAgendaItem.position")
    report_rows: Mapped[list["MeDailyFacilitatorReport"]] = relationship(back_populates="round", cascade="all, delete-orphan")


class MeDailyAgendaItem(Base):
    """One planned session of the training agenda: the drop-down of topics on the form."""

    __tablename__ = "me_daily_agenda"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("me_daily_round.id", ondelete="CASCADE"), nullable=False, index=True)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    planned_start: Mapped[str | None] = mapped_column(String(5))  # HH:MM
    planned_end: Mapped[str | None] = mapped_column(String(5))
    details: Mapped[str | None] = mapped_column(Text)  # the chapter sections the session covers
    responsible: Mapped[str | None] = mapped_column(String(200))

    round: Mapped[MeDailyRound] = relationship(back_populates="agenda")


class MeDailyFacilitatorReport(TimestampMixin, Base):
    """One lead facilitator's report for one class on one day (sections A, C to H of the template).
    Repeating tables (sessions, materials issues, escalations) are JSON lists validated by the schema."""

    __tablename__ = "me_daily_facilitator_report"
    __table_args__ = (Index("ix_me_daily_fr_round_date", "round_id", "report_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("me_daily_round.id", ondelete="CASCADE"), nullable=False, index=True)
    # A identification
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    platform_venue: Mapped[str] = mapped_column(String(160), nullable=False)
    class_hall: Mapped[str] = mapped_column(String(80), nullable=False)
    training_day: Mapped[int] = mapped_column(Integer, nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    lead_facilitator: Mapped[str] = mapped_column(String(160), nullable=False)
    co_facilitators: Mapped[str | None] = mapped_column(String(300))
    district: Mapped[str | None] = mapped_column(String(60))  # blank = national / HQ
    # C schedule and content coverage
    sessions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON [{topic, planned_start, planned_end, actual_start, actual_end, delivered, delta, reason}]
    carried_over: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON [topic]
    # D participant performance and learning
    quiz_administered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quiz_title: Mapped[str | None] = mapped_column(String(200))
    mean_score: Mapped[float | None] = mapped_column(Float)  # %
    pass_rate: Mapped[float | None] = mapped_column(Float)  # %
    quiz_comments: Mapped[str | None] = mapped_column(Text)
    practice_minutes: Mapped[int | None] = mapped_column(Integer)
    practice_comments: Mapped[str | None] = mapped_column(Text)
    hardest_topics: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON [topic]
    hardest_comments: Mapped[str | None] = mapped_column(Text)
    # E facilitation quality (1 to 5)
    q_content: Mapped[int] = mapped_column(Integer, nullable=False)
    q_content_evidence: Mapped[str | None] = mapped_column(Text)
    q_engagement: Mapped[int] = mapped_column(Integer, nullable=False)
    q_engagement_evidence: Mapped[str | None] = mapped_column(Text)
    q_time: Mapped[int] = mapped_column(Integer, nullable=False)
    q_time_evidence: Mapped[str | None] = mapped_column(Text)
    q_illustrations: Mapped[int] = mapped_column(Integer, nullable=False)
    q_illustrations_evidence: Mapped[str | None] = mapped_column(Text)
    overall: Mapped[float] = mapped_column(Float, nullable=False)  # mean of the four
    # F materials and assessment issues log
    material_issues: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON [{item, type, severity, correction}]
    # G connectivity, power and logistics
    g_internet: Mapped[int] = mapped_column(Integer, nullable=False)
    g_internet_details: Mapped[str | None] = mapped_column(Text)
    g_power: Mapped[int] = mapped_column(Integer, nullable=False)
    g_power_details: Mapped[str | None] = mapped_column(Text)
    g_devices: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    g_devices_details: Mapped[str | None] = mapped_column(Text)
    g_food: Mapped[int] = mapped_column(Integer, nullable=False)
    g_food_details: Mapped[str | None] = mapped_column(Text)
    # H escalations and decisions needed
    escalations: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON [{issue, raised_to, owner, needed_by, status}]
    # bookkeeping
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edit_token_hash: Mapped[str | None] = mapped_column(String(64))
    edited_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    round: Mapped[MeDailyRound] = relationship(back_populates="report_rows")
