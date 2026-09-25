"""Field Exit Protocol: the Data Quality Manager check-out form for
supervisors and enumerators, one record per field staff member."""

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class StaffRole(str, enum.Enum):
    ENUMERATOR = "ENUMERATOR"
    SUPERVISOR = "SUPERVISOR"


class CheckoutStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"  # District DQM certified
    NATIONAL_SIGNED = "NATIONAL_SIGNED"  # National DQM countersigned
    CLEARED = "CLEARED"  # Director's decision recorded


class ClearanceDecision(str, enum.Enum):
    CLEARED_PAYMENT = "CLEARED_PAYMENT"
    CLEARED_REDEPLOYMENT = "CLEARED_REDEPLOYMENT"
    CONDITIONAL = "CONDITIONAL"
    NOT_CLEARED = "NOT_CLEARED"


class ExitCheckout(TimestampMixin, Base):
    __tablename__ = "exit_checkout"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("team.id"))
    status: Mapped[CheckoutStatus] = mapped_column(Enum(CheckoutStatus, name="checkout_status"), default=CheckoutStatus.DRAFT, nullable=False, index=True)

    # A. Field staff details
    staff_name: Mapped[str] = mapped_column(String(160), nullable=False)
    login_id: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[StaffRole] = mapped_column(Enum(StaffRole, name="staff_role"), nullable=False, index=True)
    sa_ea_codes: Mapped[str | None] = mapped_column(String(255))

    # B. Workload completion and data validation: 12 rows as JSON [{n, answer, remarks}]
    checklist: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    enumerator_conduct: Mapped[str | None] = mapped_column(Text)

    # C. Supervisor final sync and retrieval: JSON [{item, returned, condition, clearance}]
    items: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    supervisor_conduct: Mapped[str | None] = mapped_column(Text)

    # Certification and approval (names/comments typed in; the two DQM roles also sign in-app)
    approvals: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    national_signed_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    national_signed_name: Mapped[str | None] = mapped_column(String(160))
    national_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    national_comment: Mapped[str | None] = mapped_column(Text)

    # D. Clearance by the Director, Data Science Division
    decision: Mapped[ClearanceDecision | None] = mapped_column(Enum(ClearanceDecision, name="clearance_decision"), index=True)
    outstanding_issues: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[date | None] = mapped_column(Date)
    decided_name: Mapped[str | None] = mapped_column(String(160))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    deleted_by: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    delete_reason: Mapped[str | None] = mapped_column(Text)
