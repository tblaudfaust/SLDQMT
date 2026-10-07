"""M&E Field Monitoring: the geography below the district (chiefdoms and sections) and frame versions.

EAs stay in the existing `ea` table (one row per EA, under its supervisory area), which gains the
10-digit POP_EA_CODE, chiefdom and section codes, the rural/urban status and the expected households.
"""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


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
