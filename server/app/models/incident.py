"""Census Incident Log: incidents, their dated updates, and the supervisory-area codes supervisors
report with on the public page (docs/census-incident-log-design.md)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Incident(TimestampMixin, Base):
    __tablename__ = "incident"
    __table_args__ = (Index("ix_incident_district_status", "district_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)  # INC-Bo-202611-0042
    # who reported
    reported_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))  # None for the public page
    reporter_name: Mapped[str | None] = mapped_column(String(160))
    reporter_role: Mapped[str | None] = mapped_column(String(32))
    reporter_phone: Mapped[str | None] = mapped_column(String(32))
    sa_code: Mapped[str | None] = mapped_column(String(16), index=True)  # the 12-digit code typed on the public page
    sa_recognised: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    track_token_hash: Mapped[str | None] = mapped_column(String(64))  # lets the public reporter follow the incident
    # where and when
    district_id: Mapped[int | None] = mapped_column(ForeignKey("district.id"), index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("team.id"), index=True)
    ea_code: Mapped[str | None] = mapped_column(String(16))
    locality: Mapped[str | None] = mapped_column(String(200))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    phase: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # what
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[str | None] = mapped_column(Text)
    help_needed: Mapped[str | None] = mapped_column(Text)
    teams_affected: Mapped[int | None] = mapped_column(Integer)
    staff_affected: Mapped[int | None] = mapped_column(Integer)
    households_affected: Mapped[int | None] = mapped_column(Integer)
    days_lost: Mapped[int | None] = mapped_column(Integer)
    asset_tags: Mapped[str | None] = mapped_column(String(300))  # tablets involved, comma separated
    reference: Mapped[str | None] = mapped_column(String(200))  # linked record (error id, visit, report number)
    # handling
    status: Mapped[str] = mapped_column(String(16), default="NEW", nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(16), default="DISTRICT", nullable=False)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(Text)
    root_cause_fixed: Mapped[bool | None] = mapped_column(Boolean)
    lessons: Mapped[str | None] = mapped_column(Text)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    updates: Mapped[list["IncidentUpdate"]] = relationship(back_populates="incident", cascade="all, delete-orphan", order_by="IncidentUpdate.at")


class IncidentUpdate(Base):
    """One dated entry of the incident's log: a comment, a status change, an assignment, an escalation."""

    __tablename__ = "incident_update"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id", ondelete="CASCADE"), nullable=False, index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    author_name: Mapped[str | None] = mapped_column(String(160))
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    text: Mapped[str | None] = mapped_column(Text)
    old_value: Mapped[str | None] = mapped_column(String(200))
    new_value: Mapped[str | None] = mapped_column(String(200))

    incident: Mapped[Incident] = relationship(back_populates="updates")


class IncidentSaCode(TimestampMixin, Base):
    """The supervisory-area codes supervisors type on the public page, uploaded by HQ with their district."""

    __tablename__ = "incident_sa_code"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sa_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("district.id"), index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("team.id"))
    sa_name: Mapped[str | None] = mapped_column(String(160))
    supervisor_name: Mapped[str | None] = mapped_column(String(160))
    supervisor_phone: Mapped[str | None] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
