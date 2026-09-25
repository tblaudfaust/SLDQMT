from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Setting(TimestampMixin, Base):
    __tablename__ = "setting"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)


DEFAULT_SETTINGS = {
    "follow_up_interval_hours": "4",
    "quiet_hours_start": "20:00",
    "quiet_hours_end": "07:00",
    "offline_days": "14",
}
