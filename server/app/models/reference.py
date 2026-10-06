from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Region(TimestampMixin, Base):
    __tablename__ = "region"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    districts: Mapped[list["District"]] = relationship(back_populates="region")


class District(TimestampMixin, Base):
    __tablename__ = "district"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("region.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    region: Mapped[Region] = relationship(back_populates="districts")
    teams: Mapped[list["Team"]] = relationship(back_populates="district")


class Team(TimestampMixin, Base):
    """A supervisory area (SA) team: one supervisor, several enumerators, several EAs."""

    __tablename__ = "team"
    __table_args__ = (UniqueConstraint("district_id", "code", name="uq_team_code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    chiefdom: Mapped[str | None] = mapped_column(String(120))
    local_council: Mapped[str | None] = mapped_column(String(120))
    ea_count: Mapped[int | None] = mapped_column(Integer)
    # Workload (FIELD_MONITOR sheet): the Field Monitor and the DQM officer responsible for this SA,
    # e.g. FM-11-001 and DQM-11-001. Accounts link to their SAs through User.staff_code.
    monitor_code: Mapped[str | None] = mapped_column(String(32), index=True)
    dqm_code: Mapped[str | None] = mapped_column(String(32), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    district: Mapped[District] = relationship(back_populates="teams")
    supervisors: Mapped[list["Supervisor"]] = relationship(back_populates="team")
    enumerators: Mapped[list["Enumerator"]] = relationship(back_populates="team")
    eas: Mapped[list["EnumerationArea"]] = relationship(back_populates="team")


class Supervisor(TimestampMixin, Base):
    __tablename__ = "supervisor"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(32))
    external_id: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    team: Mapped[Team] = relationship(back_populates="supervisors")


class Enumerator(TimestampMixin, Base):
    __tablename__ = "enumerator"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(32))
    external_id: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    team: Mapped[Team] = relationship(back_populates="enumerators")


class EnumerationArea(TimestampMixin, Base):
    __tablename__ = "ea"
    __table_args__ = (UniqueConstraint("team_id", "code", name="uq_ea_code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(160))
    locality: Mapped[str | None] = mapped_column(String(160))
    households: Mapped[int | None] = mapped_column(Integer)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    team: Mapped[Team] = relationship(back_populates="eas")


class ErrorCategory(TimestampMixin, Base):
    __tablename__ = "error_category"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class ErrorSource(TimestampMixin, Base):
    __tablename__ = "error_source"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
