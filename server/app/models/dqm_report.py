"""Annex A: the 2026 SLPHC Data Quality Management Daily Reporting Tool,
completed by each DQM officer once per district per day."""

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ReportPeriod(str, enum.Enum):
    LISTING = "LISTING"
    ENUMERATION = "ENUMERATION"


class ReportStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    RECEIVED = "RECEIVED"


class DqmDailyReport(TimestampMixin, Base):
    __tablename__ = "dqm_daily_report"
    # One live report per DQM officer (created_by) per district per day is enforced in the service:
    # several officers work in the same district and each sends their own report. Deleted reports
    # are kept for the audit trail, so a plain unique constraint would block re-entry.
    __table_args__ = (Index("ix_dqm_report_day", "district_id", "report_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False, index=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period: Mapped[ReportPeriod] = mapped_column(Enum(ReportPeriod, name="report_period"), nullable=False)
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(Enum(ReportStatus, name="report_status"), default=ReportStatus.DRAFT, nullable=False, index=True)

    # 1. Executive data-quality summary (cumulative)
    teams_reviewed: Mapped[int | None] = mapped_column(Integer)
    teams_certified: Mapped[int | None] = mapped_column(Integer)
    executive_summary: Mapped[str | None] = mapped_column(Text)

    # 2. Re-interview and certification
    reinterviews_received: Mapped[int | None] = mapped_column(Integer)
    reinterviews_received_pending: Mapped[int | None] = mapped_column(Integer)
    reinterviews_received_remarks: Mapped[str | None] = mapped_column(Text)
    reinterviews_certified: Mapped[int | None] = mapped_column(Integer)
    reinterviews_certified_pending: Mapped[int | None] = mapped_column(Integer)
    reinterviews_certified_remarks: Mapped[str | None] = mapped_column(Text)

    # 3 to 6: repeating rows, stored as JSON text and validated by the schemas
    error_profile: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    system_issues: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    lessons: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    sa_performance: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    # Certification and submission
    prepared_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    prepared_name: Mapped[str | None] = mapped_column(String(160))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    received_name: Mapped[str | None] = mapped_column(String(160))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    receiver_comment: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    delete_reason: Mapped[str | None] = mapped_column(Text)
