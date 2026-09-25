import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import utcnow


class ErrorStatus(str, enum.Enum):
    UNRESOLVED = "UNRESOLVED"
    RESOLVED = "RESOLVED"


class SupportMethod(str, enum.Enum):
    REMOTE = "REMOTE"
    ONSITE = "ONSITE"


class ErrorRecord(Base):
    """One data-quality error logged by a Field Monitor. The row id is the
    tablet-generated UUID, which makes pushes idempotent."""

    __tablename__ = "error"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(String(36))

    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("team.id"), index=True)
    supervisor_id: Mapped[int | None] = mapped_column(ForeignKey("supervisor.id"))
    supervisor_name: Mapped[str | None] = mapped_column(String(160))
    enumerator_id: Mapped[int | None] = mapped_column(ForeignKey("enumerator.id"))
    enumerator_name: Mapped[str | None] = mapped_column(String(160))
    ea_id: Mapped[int | None] = mapped_column(ForeignKey("ea.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("error_category.id"), nullable=False, index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("error_source.id"))

    description: Mapped[str] = mapped_column(Text, nullable=False)
    date_received: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    support_method: Mapped[SupportMethod] = mapped_column(Enum(SupportMethod, name="support_method"), nullable=False)
    action_taken: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)

    status: Mapped[ErrorStatus] = mapped_column(Enum(ErrorStatus, name="error_status"), nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_action_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    gps_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    client_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    client_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Soft delete from the dashboard; the tablet removes its copy at the next pull.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    delete_reason: Mapped[str | None] = mapped_column(Text)

    follow_ups: Mapped[list["FollowUp"]] = relationship(back_populates="error", cascade="all, delete-orphan")
    activity: Mapped[list["Activity"]] = relationship(back_populates="error", cascade="all, delete-orphan")


class FollowUp(Base):
    __tablename__ = "follow_up"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    error_id: Mapped[str] = mapped_column(ForeignKey("error.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(36))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    method: Mapped[SupportMethod] = mapped_column(Enum(SupportMethod, name="support_method"), nullable=False)
    contacted: Mapped[str | None] = mapped_column(String(160))
    outcome: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    gps_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    error: Mapped[ErrorRecord] = relationship(back_populates="follow_ups")


class Activity(Base):
    """Append-only history entry: every status change or edit."""

    __tablename__ = "activity"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    error_id: Mapped[str] = mapped_column(ForeignKey("error.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(36))
    previous_status: Mapped[ErrorStatus | None] = mapped_column(Enum(ErrorStatus, name="error_status"))
    new_status: Mapped[ErrorStatus] = mapped_column(Enum(ErrorStatus, name="error_status"), nullable=False)
    action_taken: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)
    client_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    error: Mapped[ErrorRecord] = relationship(back_populates="activity")
