import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Role(str, enum.Enum):
    FIELD_MONITOR = "FIELD_MONITOR"
    DISTRICT_DQM = "DISTRICT_DQM"
    REGIONAL = "REGIONAL"
    NATIONAL_DQM = "NATIONAL_DQM"
    ADMIN = "ADMIN"
    ME = "ME"  # Monitoring & Evaluation: training evaluations only


# Roles that see every district; a scope row never narrows them.
UNSCOPED_ROLES = {Role.NATIONAL_DQM, Role.ADMIN, Role.ME}
WEB_ROLES = {Role.DISTRICT_DQM, Role.REGIONAL, Role.NATIONAL_DQM, Role.ADMIN, Role.ME}


class User(TimestampMixin, Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    # Staff code from the workload frame (FM-11-001 for a Field Monitor, DQM-11-001 for a District DQM):
    # the SAs whose monitor_code / dqm_code equal it are this officer's own workload.
    staff_code: Mapped[str | None] = mapped_column(String(32), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set by an administrator; the tablet wipes its PIN at the next sync and the flag clears at the next sign-in
    pin_reset_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    scopes: Mapped[list["UserScope"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserScope(Base):
    """A district or a region a user may see. Unscoped roles ignore these rows."""

    __tablename__ = "user_scope"
    __table_args__ = (UniqueConstraint("user_id", "region_id", "district_id", name="uq_user_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("region.id"))
    district_id: Mapped[int | None] = mapped_column(ForeignKey("district.id"))

    user: Mapped[User] = relationship(back_populates="scopes")


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id: Mapped[str | None] = mapped_column(String(36))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
