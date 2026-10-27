"""Daily Facilitator's Report (ToT, in-person): one report per hall per day by the Lead Facilitator, attached to a
facilitator-assessment training (the same chapters per day and the same public token family)."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.me_fac import MeFacRound
from app.models.mixins import TimestampMixin


class MeFacReport(TimestampMixin, Base):
    __tablename__ = "me_fac_report"
    __table_args__ = (Index("ix_me_fac_report_round_date", "round_id", "report_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("me_fac_round.id", ondelete="CASCADE"), nullable=False, index=True)
    # A · identification
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    training_day: Mapped[int] = mapped_column(Integer, nullable=False)
    venue: Mapped[str] = mapped_column(String(80), nullable=False)
    hall: Mapped[str] = mapped_column(String(80), nullable=False)
    lead_facilitator: Mapped[str] = mapped_column(String(160), nullable=False)
    other_facilitators: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(32))
    # B · attendance
    registered: Mapped[int] = mapped_column(Integer, nullable=False)
    present: Mapped[int] = mapped_column(Integer, nullable=False)
    # C · delivery
    delivered: Mapped[str] = mapped_column(String(8), nullable=False)  # FULL | PARTLY | NO
    missed_sessions: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON list of chapter titles
    minutes_lost: Mapped[int | None] = mapped_column(Integer)
    missed_reason: Mapped[str | None] = mapped_column(Text)
    # D · class ratings (1 to 5)
    r_knowledge: Mapped[int] = mapped_column(Integer, nullable=False)
    r_engagement: Mapped[int] = mapped_column(Integer, nullable=False)
    r_illustrations: Mapped[int] = mapped_column(Integer, nullable=False)
    r_connectivity: Mapped[int] = mapped_column(Integer, nullable=False)
    r_coordination: Mapped[int] = mapped_column(Integer, nullable=False)
    mean_rating: Mapped[float] = mapped_column(Float, nullable=False)
    # E · logistics
    e_internet: Mapped[int | None] = mapped_column(Integer)
    e_internet_details: Mapped[str | None] = mapped_column(Text)
    e_power: Mapped[int | None] = mapped_column(Integer)
    e_power_details: Mapped[str | None] = mapped_column(Text)
    e_devices: Mapped[str | None] = mapped_column(String(200))
    e_devices_details: Mapped[str | None] = mapped_column(Text)
    e_food: Mapped[str | None] = mapped_column(String(200))
    e_food_details: Mapped[str | None] = mapped_column(Text)
    # F · right, G · wrong, H · recommendations, I · closing
    went_right: Mapped[str] = mapped_column(Text, nullable=False)
    repeat_share: Mapped[str | None] = mapped_column(Text)
    went_wrong: Mapped[str] = mapped_column(Text, nullable=False)
    difficult_topics: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON list of chapter titles
    difficult_notes: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[str] = mapped_column(Text, nullable=False)
    gaps: Mapped[str] = mapped_column(Text, nullable=False)
    actors: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON list of actor codes
    actor_other: Mapped[str | None] = mapped_column(String(160))
    comments: Mapped[str | None] = mapped_column(Text)
    # bookkeeping
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    edit_token_hash: Mapped[str | None] = mapped_column(String(64))
    edited_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    round: Mapped[MeFacRound] = relationship()
