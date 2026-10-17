"""Facilitator assessment: M&E monitors rate each trainer daily in the training halls (the Daily Trainer
Facilitation Rating Tool), grouped per training with the chapters per day, shared through a link."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class MeFacRound(TimestampMixin, Base):
    """A training whose trainers are assessed daily (e.g. 'Master Trainers session, October 2026')."""

    __tablename__ = "me_fac_round"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)  # MASTER | TOT | FIELD
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    token: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False)  # OPEN | CLOSED
    created_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))

    agenda: Mapped[list["MeFacAgendaItem"]] = relationship(back_populates="round", cascade="all, delete-orphan", order_by="MeFacAgendaItem.day, MeFacAgendaItem.position")
    assessment_rows: Mapped[list["MeFacAssessment"]] = relationship(back_populates="round", cascade="all, delete-orphan")


class MeFacAgendaItem(Base):
    """One chapter or thematic section of a training day: a row of section B on the form."""

    __tablename__ = "me_fac_agenda"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("me_fac_round.id", ondelete="CASCADE"), nullable=False, index=True)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    rated: Mapped[bool | None] = mapped_column(Boolean)  # False = listed for the day but not a row of section B; NULL = rated

    round: Mapped[MeFacRound] = relationship(back_populates="agenda")


class MeFacAssessment(TimestampMixin, Base):
    """One monitor's rating of one trainer on one day in one hall."""

    __tablename__ = "me_fac_assessment"
    __table_args__ = (Index("ix_me_fac_round_date", "round_id", "assessment_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("me_fac_round.id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False)
    training_day: Mapped[int] = mapped_column(Integer, nullable=False)
    district: Mapped[str | None] = mapped_column(String(60))  # blank = national / HQ
    hall: Mapped[str] = mapped_column(String(80), nullable=False)
    monitor_name: Mapped[str] = mapped_column(String(160), nullable=False)
    trainer_name: Mapped[str] = mapped_column(String(160), nullable=False)
    # section A (1 to 4 each)
    s_technical: Mapped[int] = mapped_column(Integer, nullable=False)
    s_clarity: Mapped[int] = mapped_column(Integer, nullable=False)
    s_practical: Mapped[int] = mapped_column(Integer, nullable=False)
    s_participation: Mapped[int] = mapped_column(Integer, nullable=False)
    s_time: Mapped[int] = mapped_column(Integer, nullable=False)
    section_a_total: Mapped[int] = mapped_column(Integer, nullable=False)
    # section B: JSON [{topic, rating}] with rating 1 to 4 or null (not observed)
    sections: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    section_b_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    section_b_max: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    score_pct: Mapped[float] = mapped_column(Float, nullable=False)
    band: Mapped[str] = mapped_column(String(24), nullable=False)
    strengths: Mapped[str | None] = mapped_column(Text)
    improvements: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)
    # bookkeeping
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edit_token_hash: Mapped[str | None] = mapped_column(String(64))
    edited_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    round: Mapped[MeFacRound] = relationship(back_populates="assessment_rows")
