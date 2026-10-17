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
    # M&E field monitoring: GPS checks on submitted forms and check-ins
    "mefm_ea_distance_m": "1000",  # farther than this from the EA reference point is flagged
    "mefm_gps_accuracy_m": "50",
    "mefm_max_speed_kmh": "120",
    "mefm_night_start": "20:00",
    "mefm_night_end": "05:00",
    # phase dates (YYYY-MM-DD), set later by the M&E unit; blank means not set
    "mefm_phase_listing_start": "",
    "mefm_phase_enumeration_start": "",
    "mefm_phase_mopup_start": "",
    "mefm_phase_end": "",
    # Census incident log: default time to resolve by severity (hours); overdue is shown on the dashboard, never escalated automatically
    "incident_due_hours_critical": "24",
    "incident_due_hours_major": "72",
    "incident_due_hours_minor": "168",
}
