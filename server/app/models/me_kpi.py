"""M&E Field Tool: KPI reports the M&E team collects in the field (online or offline, synced later)."""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class MeKpiReport(TimestampMixin, Base):
    """One form: an SA (or practice team) on one day, with the answers to the 11 KPIs and section B."""

    __tablename__ = "me_kpi_report"
    __table_args__ = (Index("ix_me_kpi_district_date", "district_id", "report_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[str] = mapped_column(String(48), unique=True, nullable=False, index=True)  # set by the device, makes offline sync idempotent
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)  # the M&E officer
    # Section A
    phase: Mapped[str] = mapped_column(String(8), nullable=False)  # MT | TOT | TOE | L | E
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    week: Mapped[int | None] = mapped_column(Integer)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("district.id"), index=True)
    chiefdom: Mapped[str | None] = mapped_column(String(160))
    section: Mapped[str | None] = mapped_column(String(160))
    team_id: Mapped[int | None] = mapped_column(ForeignKey("team.id"), index=True)
    sa_code: Mapped[str | None] = mapped_column(String(32))
    ea_codes: Mapped[str | None] = mapped_column(Text)  # JSON list: the EAs of the SA the visit covered
    practice_team: Mapped[str | None] = mapped_column(String(120))  # field practice: team / hall name
    respondent_name: Mapped[str | None] = mapped_column(String(160))
    respondent_role: Mapped[str | None] = mapped_column(String(24))
    eas_urban: Mapped[int | None] = mapped_column(Integer)
    eas_rural: Mapped[int | None] = mapped_column(Integer)
    enumerators: Mapped[int | None] = mapped_column(Integer)
    capi_version: Mapped[str | None] = mapped_column(String(40))
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    # answers (JSON by item code) and the computed figures
    answers: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    coverage_pct: Mapped[float | None] = mapped_column(Float)
    synced_pct: Mapped[float | None] = mapped_column(Float)
    error_pct: Mapped[float | None] = mapped_column(Float)
    tablets_pct: Mapped[float | None] = mapped_column(Float)
    overall: Mapped[int | None] = mapped_column(Integer)
    safety_concern: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # bookkeeping
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    device: Mapped[str | None] = mapped_column(String(160))
    edited_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
