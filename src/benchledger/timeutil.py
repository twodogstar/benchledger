"""Time handling (requirement N7): store UTC with the source offset, display local time.

"Local" means the time zone of the machine BenchLedger runs on, unless a zone is passed in
(tests pass America/Los_Angeles so they don't depend on the machine).

SQLite has no time-zone-aware type: SQLAlchemy writes datetimes as text without an offset
and reads them back naive. So everything written is converted to UTC first, and anything
read back naive is taken to be UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime, tzinfo

FORM_FORMAT = "%Y-%m-%dT%H:%M"  # what an <input type="datetime-local"> sends and shows
# Sane bounds for a bench notebook; also keeps clear of datetime overflow at year 1 and 9999.
MIN_YEAR = 1900
MAX_YEAR = 2200


def as_utc(value: datetime) -> datetime:
    """An aware UTC datetime. Naive values are assumed to be UTC (as read from SQLite)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def now_utc() -> datetime:
    return datetime.now(UTC)


def now_with_offset(tz: tzinfo | None = None) -> tuple[datetime, int]:
    """The current minute as (UTC datetime, local offset in minutes)."""
    local = to_local(now_utc(), tz).replace(second=0, microsecond=0)
    return local.astimezone(UTC), offset_minutes(local)


def offset_minutes(value: datetime) -> int:
    """The UTC offset of an aware datetime, in whole minutes."""
    offset = value.utcoffset()
    if offset is None:
        raise ValueError("offset_minutes needs a time-zone-aware datetime")
    return int(offset.total_seconds() // 60)


def from_local(naive: datetime, tz: tzinfo | None = None) -> tuple[datetime, int]:
    """Read a wall-clock time in local time. Returns (UTC datetime, source offset in minutes).

    During a daylight-saving fall-back the repeated hour is read as its first occurrence
    (fold=0), which is the usual reading of an ambiguous time. A time that doesn't exist
    (skipped by a spring-forward) moves to the real instant it lands on, and the offset
    is taken from that instant so the two always agree.
    Raises ValueError for years outside MIN_YEAR..MAX_YEAR.
    """
    if naive.tzinfo is not None:
        raise ValueError("from_local expects a naive wall-clock time")
    if not MIN_YEAR <= naive.year <= MAX_YEAR:
        raise ValueError(f"year must be between {MIN_YEAR} and {MAX_YEAR}")
    # naive.astimezone() interprets a naive time in the machine's own zone, DST included.
    aware = naive.replace(tzinfo=tz) if tz is not None else naive.astimezone()
    utc = aware.astimezone(UTC)
    back = utc.astimezone(tz) if tz is not None else utc.astimezone()
    return utc, offset_minutes(back)


def parse_local(text: str, tz: tzinfo | None = None) -> tuple[datetime, int]:
    """Parse a datetime-local form value ('2026-11-01T01:30'). Raises ValueError if invalid."""
    naive = datetime.strptime(text.strip(), FORM_FORMAT)
    return from_local(naive, tz)


def to_local(value: datetime, tz: tzinfo | None = None) -> datetime:
    """Convert a stored (UTC) datetime to local time for display."""
    utc = as_utc(value)
    return utc.astimezone(tz) if tz is not None else utc.astimezone()


def format_offset(minutes: int) -> str:
    """-420 -> 'UTC-07:00'."""
    sign = "-" if minutes < 0 else "+"
    hours, mins = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours:02d}:{mins:02d}"


def display(value: datetime | None, tz: tzinfo | None = None) -> str:
    """A stored datetime as local time for pages: '2026-10-31 18:20 PDT'."""
    if value is None:
        return ""
    return to_local(value, tz).strftime("%Y-%m-%d %H:%M %Z").strip()


def iso_utc(value: datetime | None) -> str:
    """Machine-readable UTC for <time datetime="…">: '2026-11-01T01:20:00Z'."""
    if value is None:
        return ""
    return as_utc(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def display_utc(value: datetime | None) -> str:
    if value is None:
        return ""
    return as_utc(value).strftime("%Y-%m-%d %H:%M UTC")


def form_value(value: datetime, tz: tzinfo | None = None) -> str:
    """A stored datetime as a datetime-local form value, in local time."""
    return to_local(value, tz).strftime(FORM_FORMAT)
