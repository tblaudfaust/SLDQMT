from datetime import datetime, time, timezone

from app.services.followup import FollowUpPolicy, in_quiet_window, next_follow_up

POLICY = FollowUpPolicy(interval_hours=4, quiet_start=time(20, 0), quiet_end=time(7, 0))


def test_daytime_action_due_in_four_hours():
    at = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
    assert next_follow_up(at, POLICY) == datetime(2026, 9, 24, 13, 0, tzinfo=timezone.utc)


def test_evening_action_moves_to_next_morning():
    at = datetime(2026, 9, 24, 18, 30, tzinfo=timezone.utc)
    assert next_follow_up(at, POLICY) == datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc)


def test_late_night_action_moves_to_same_morning():
    at = datetime(2026, 9, 25, 1, 0, tzinfo=timezone.utc)
    assert next_follow_up(at, POLICY) == datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc)


def test_quiet_window_edges():
    assert in_quiet_window(datetime(2026, 9, 24, 20, 0, tzinfo=timezone.utc), POLICY)
    assert not in_quiet_window(datetime(2026, 9, 24, 7, 0, tzinfo=timezone.utc), POLICY)
    assert not in_quiet_window(datetime(2026, 9, 24, 19, 59, tzinfo=timezone.utc), POLICY)


def test_naive_datetime_treated_as_utc():
    at = datetime(2026, 9, 24, 9, 0)
    assert next_follow_up(at, POLICY).tzinfo is not None
