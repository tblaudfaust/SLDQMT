"""Monitoring & Evaluation: training evaluations shared by link, their respondents and responses."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class MeEvaluation(TimestampMixin, Base):
    """One evaluation round (a training cohort), shared with trainees and trainers through its link."""

    __tablename__ = "me_evaluation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    training_mode: Mapped[str] = mapped_column(String(16), nullable=False)  # ONLINE | IN_PERSON
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    token: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)  # the share link
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False)  # OPEN | CLOSED
    created_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))

    respondents: Mapped[list["MeRespondent"]] = relationship(back_populates="evaluation", cascade="all, delete-orphan")
    responses: Mapped[list["MeResponse"]] = relationship(back_populates="evaluation", cascade="all, delete-orphan")


class MeRespondent(TimestampMixin, Base):
    """A trainee or trainer who registered on the evaluation page with their email and phone."""

    __tablename__ = "me_respondent"
    __table_args__ = (UniqueConstraint("evaluation_id", "email", name="uq_me_respondent_email"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("me_evaluation.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    resume_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # proves the browser that registered is the one submitting
    district: Mapped[str | None] = mapped_column(String(60))  # chosen at registration; pre-fills A04 and drives the district reports
    attendance_mode: Mapped[str | None] = mapped_column(String(16))  # ONLINE | IN_PERSON, how this person took the training
    hall: Mapped[str | None] = mapped_column(String(60))  # training hall / venue number for in-person attendance

    evaluation: Mapped[MeEvaluation] = relationship(back_populates="respondents")
    response: Mapped["MeResponse | None"] = relationship(back_populates="respondent", uselist=False)


class MeResponse(TimestampMixin, Base):
    """The submitted questionnaire of one respondent (one per respondent and evaluation)."""

    __tablename__ = "me_response"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("me_evaluation.id", ondelete="CASCADE"), nullable=False, index=True)
    respondent_id: Mapped[int] = mapped_column(ForeignKey("me_respondent.id", ondelete="CASCADE"), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # TRAINER | TRAINEE | NEITHER (from A00)
    answers: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # JSON, item code -> value (asked items only)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # excluded from results; kept for the audit trail
    user_agent: Mapped[str | None] = mapped_column(String(300))

    evaluation: Mapped[MeEvaluation] = relationship(back_populates="responses")
    respondent: Mapped[MeRespondent] = relationship(back_populates="response")
