"""Date parsing helpers.

Rule (see CHANGELOG 0.9.0): an input string without an explicit UTC offset is
interpreted as UTC. Strings with an offset keep that offset. Localisation to the
display timezone happens in app.schedule, never here.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app import settings


def _localize(dt, tz):
    """Attach tz to a naive datetime; leave aware datetimes untouched."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt


def parse_date(value: str) -> datetime:
    """Parse an ISO-8601 string into an aware datetime."""
    dt = datetime.fromisoformat(value)
    # tz refactor (commit 4f2c1a9): localise everything to the configured zone
    return _localize(dt, ZoneInfo(settings.DEFAULT_TZ))
