"""Daily Evaluation: the Daily Trainer Class Evaluation form, one per class per day, grouped in rounds
(a training event) that are shared with lead trainers through a link."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class MeDailyRound(TimestampMixin, Base):
    """A training event whose classes report daily (e.g. 'Field staff training, Southern region')."""

    __tablename__ = "me_daily_round"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)  # MASTER | TOT | FIELD (default for the form)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    token: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False)  # OPEN | CLOSED
    created_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))

    report_rows: Mapped[list["MeDailyReport"]] = relationship(back_populates="round", cascade="all, delete-orphan")


class MeDailyReport(TimestampMixin, Base):
    """One lead trainer's form for one class on one day. Every field of the paper form is a column so
    the reports and exports can show each detail."""

    __tablename__ = "me_daily_report"
    __table_args__ = (Index("ix_me_daily_report_round_date", "round_id", "report_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("me_daily_round.id", ondelete="CASCADE"), nullable=False, index=True)
    # context
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    training_day: Mapped[int] = mapped_column(Integer, nullable=False)
    class_hall: Mapped[str] = mapped_column(String(80), nullable=False)
    venue: Mapped[str | None] = mapped_column(String(160))
    lead_trainer: Mapped[str] = mapped_column(String(160), nullable=False)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    district: Mapped[str | None] = mapped_column(String(60))  # blank = national / HQ
    # 1 attendance and delivery
    expected: Mapped[int] = mapped_column(Integer, nullable=False)
    present: Mapped[int] = mapped_column(Integer, nullable=False)
    late: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    coverage: Mapped[str] = mapped_column(String(8), nullable=False)  # ALL | SOME | NONE
    incomplete_topic: Mapped[str | None] = mapped_column(Text)
    practice_minutes: Mapped[int | None] = mapped_column(Integer)
    practice_not_scheduled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 2 learning evidence
    checks: Mapped[str] = mapped_column(String(64), default="", nullable=False)  # comma separated: QUIZ, PRACTICAL, ORAL or NOT_ASSESSED
    task_checked: Mapped[str | None] = mapped_column(Text)
    number_checked: Mapped[int | None] = mapped_column(Integer)
    number_met: Mapped[int | None] = mapped_column(Integer)
    criterion: Mapped[str | None] = mapped_column(Text)
    learning_gap: Mapped[str | None] = mapped_column(Text)
    followup_count: Mapped[int | None] = mapped_column(Integer)
    followup_not_assessed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 3 delivery and support
    delivery_content: Mapped[str] = mapped_column(String(8), nullable=False)  # GOOD | SOME | MAJOR
    delivery_participation: Mapped[str] = mapped_column(String(8), nullable=False)
    delivery_time: Mapped[str] = mapped_column(String(8), nullable=False)
    support: Mapped[str] = mapped_column(String(120), default="", nullable=False)  # comma separated codes
    support_other: Mapped[str | None] = mapped_column(Text)
    # 4 priority actions
    actions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON [{issue, action, owner_due}]
    mgmt_help: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raised_to: Mapped[str | None] = mapped_column(String(160))
    # bookkeeping
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edit_token_hash: Mapped[str | None] = mapped_column(String(64))  # lets the trainer's browser correct its own report
    edited_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))  # a manager who edited it on the dashboard
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    round: Mapped[MeDailyRound] = relationship(back_populates="report_rows")
