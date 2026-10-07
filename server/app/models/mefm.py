"""M&E Field Monitoring: the geography below the district (chiefdoms and sections) and frame versions.

EAs stay in the existing `ea` table (one row per EA, under its supervisory area), which gains the
10-digit POP_EA_CODE, chiefdom and section codes, the rural/urban status and the expected households.
"""

import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, utcnow


class MefmChiefdom(TimestampMixin, Base):
    __tablename__ = "mefm_chiefdom"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)  # CHFDM_CODE, 5 digits
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MefmSection(TimestampMixin, Base):
    __tablename__ = "mefm_section"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False, index=True)
    chiefdom_id: Mapped[int] = mapped_column(ForeignKey("mefm_chiefdom.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)  # SECT_CODE, 7 digits
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MefmFrameVersion(TimestampMixin, Base):
    """One applied frame upload: what the file held and what it changed."""

    __tablename__ = "mefm_frame_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    applied_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    counts: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # JSON: new rows per level
    changes: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # JSON: updated names, codes missing from the file
    note: Mapped[str | None] = mapped_column(Text)


class VisitStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"  # received from the tablet
    REVIEWED = "REVIEWED"  # a reviewer has looked at it (stage 3)


class IssueStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"


class MefmVisit(Base):
    """One completed monitoring form (sections A to J) for one EA on one day.

    The answers are kept as JSON exactly as validated against app.core.mefm_form; the columns
    repeat the identification items the dashboards filter and join on. The id is the UUID the
    tablet generated, so a push repeated after a lost response is a duplicate, not a second visit."""

    __tablename__ = "mefm_visit"
    __table_args__ = (Index("ix_mefm_visit_district_date", "district_id", "visit_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("device.id"))
    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False, index=True)
    chiefdom_id: Mapped[int | None] = mapped_column(ForeignKey("mefm_chiefdom.id"), index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("mefm_section.id"), index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("team.id"), index=True)
    ea_id: Mapped[int | None] = mapped_column(ForeignKey("ea.id"), index=True)
    pop_ea_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # A8, as typed
    visit_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)  # A2
    phase: Mapped[str] = mapped_column(String(1), nullable=False)  # A12
    visit_type: Mapped[str | None] = mapped_column(String(1))  # A14
    arrived: Mapped[str | None] = mapped_column(String(5))  # A3
    left: Mapped[str | None] = mapped_column(String(5))
    team_found: Mapped[bool | None] = mapped_column(Boolean)  # A16
    # A15: the monitoring point, captured by the device, never typed
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    gps_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    distance_to_ea_m: Mapped[float | None] = mapped_column(Float)  # to the EA reference point, when it has one
    flags: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON list: far_from_ea, poor_accuracy, night, repeated_point, too_fast
    answers: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # JSON, validated
    indicators: Mapped[str] = mapped_column(Text, default="{}", nullable=False)  # JSON, computed per visit
    overall_rating: Mapped[int | None] = mapped_column(Integer)  # J7 (mean of J1 to J6)
    critical_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[VisitStatus] = mapped_column(Enum(VisitStatus, name="mefm_visit_status"), default=VisitStatus.SUBMITTED, nullable=False, index=True)
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    app_version: Mapped[str | None] = mapped_column(String(32))
    client_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    client_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    server_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    issues: Mapped[list["MefmIssue"]] = relationship(back_populates="visit", cascade="all, delete-orphan")


class MefmIssue(TimestampMixin, Base):
    """A J-1 issues log row: typed by the officer, or added automatically for a flagged item coded as a problem."""

    __tablename__ = "mefm_issue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[str] = mapped_column(ForeignKey("mefm_visit.id"), nullable=False, index=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False, index=True)
    question: Mapped[str | None] = mapped_column(String(20))  # item code, e.g. C5
    severity: Mapped[str] = mapped_column(String(10), nullable=False)  # Critical | Major | Minor
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str | None] = mapped_column(Text)
    referred_to: Mapped[str | None] = mapped_column(String(60))
    deadline: Mapped[date | None] = mapped_column(Date)
    auto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[IssueStatus] = mapped_column(Enum(IssueStatus, name="mefm_issue_status"), default=IssueStatus.OPEN, nullable=False, index=True)
    resolution: Mapped[str | None] = mapped_column(Text)
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    visit: Mapped[MefmVisit] = relationship(back_populates="issues")


class MefmCheckin(Base):
    """A GPS check-in at chiefdom or section level: where the officer was, without a full form."""

    __tablename__ = "mefm_checkin"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(ForeignKey("device.id"))
    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False, index=True)
    chiefdom_id: Mapped[int | None] = mapped_column(ForeignKey("mefm_chiefdom.id"), index=True)
    section_id: Mapped[int | None] = mapped_column(ForeignKey("mefm_section.id"), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    flags: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    server_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
