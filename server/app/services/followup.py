"""Follow-up timing: next follow-up is `interval` hours after the last action,
pushed past the quiet window when it would land inside it. Sierra Leone runs
on UTC, so quiet hours are evaluated in UTC."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import DEFAULT_SETTINGS, Setting


@dataclass(frozen=True)
class FollowUpPolicy:
    interval_hours: float = 4.0
    quiet_start: time = time(20, 0)
    quiet_end: time = time(7, 0)

    @property
    def interval(self) -> timedelta:
        return timedelta(hours=self.interval_hours)


def _parse_time(value: str, fallback: time) -> time:
    try:
        hh, mm = value.split(":")
        return time(int(hh), int(mm))
    except (ValueError, AttributeError):
        return fallback


def load_policy(db: Session) -> FollowUpPolicy:
    rows = {s.key: s.value for s in db.query(Setting).all()}
    merged = {**DEFAULT_SETTINGS, **rows}
    try:
        interval = float(merged["follow_up_interval_hours"])
    except ValueError:
        interval = 4.0
    return FollowUpPolicy(
        interval_hours=interval,
        quiet_start=_parse_time(merged["quiet_hours_start"], time(20, 0)),
        quiet_end=_parse_time(merged["quiet_hours_end"], time(7, 0)),
    )


def in_quiet_window(at: datetime, policy: FollowUpPolicy) -> bool:
    t = at.astimezone(timezone.utc).time()
    if policy.quiet_start <= policy.quiet_end:
        return policy.quiet_start <= t < policy.quiet_end
    # Window crosses midnight, e.g. 20:00 to 07:00
    return t >= policy.quiet_start or t < policy.quiet_end


def next_follow_up(last_action_at: datetime, policy: FollowUpPolicy) -> datetime:
    if last_action_at.tzinfo is None:
        last_action_at = last_action_at.replace(tzinfo=timezone.utc)
    due = last_action_at.astimezone(timezone.utc) + policy.interval
    if not in_quiet_window(due, policy):
        return due
    # Move to the end of the quiet window (today or tomorrow).
    end_today = due.replace(hour=policy.quiet_end.hour, minute=policy.quiet_end.minute, second=0, microsecond=0)
    if end_today <= due:
        end_today += timedelta(days=1)
    return end_today
