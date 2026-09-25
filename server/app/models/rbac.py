from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin
from app.models.user import Role


class RolePermission(TimestampMixin, Base):
    """One row per (role, permission) the role holds."""

    __tablename__ = "role_permission"
    __table_args__ = (UniqueConstraint("role", "code", name="uq_role_permission"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role: Mapped[Role] = mapped_column(Enum(Role, name="user_role"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)


class UserPermission(TimestampMixin, Base):
    """A per-user override: granted=True adds a permission the role lacks,
    granted=False removes one the role has."""

    __tablename__ = "user_permission"
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_user_permission"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
