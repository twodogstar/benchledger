"""Parser for the legacy logger CSV, run package format v0 (M8, R1).

The file looks like this (header lines may end in LF or CRLF):

    # instrument: HEWLETT-PACKARD,34401A,0,4-1-1
    # settings: DCV 10V range, NPLC 100, autozero ON, Zin >10GOhm, interval 0.0s
    # started: 2026-10-31T23:17:23
    timestamp,elapsed_s,volts,delta_ppm
    2026-10-31T23:17:26,3.4,7.05483570,+0.000

Rules (docs/design.md, "Legacy CSV (format v0) import"):

- Timestamps are America/Los_Angeles local time with no offset. They are converted to UTC.
  During the repeated hour when daylight saving ends, the reading's elapsed_s decides
  which of the two possible times is meant.
- elapsed_s decides the order of readings.
- Values are kept exactly as written (Decimal, never float).
- delta_ppm is not imported; it is recalculated later from a chosen baseline.
- The format has no per-reading uncertainty. The channel says so (uncertainty=None)
  and a warning is added, so the gap is never silent.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

SOURCE_TZ = ZoneInfo("America/Los_Angeles")
FORMAT_VERSION = 0
NO_UNCERTAINTY_WARNING = "legacy format: no per-reading uncertainty recorded"

REQUIRED_COLUMNS = ("timestamp", "elapsed_s", "volts")
IGNORED_COLUMNS = ("delta_ppm",)
REQUIRED_HEADERS = ("instrument", "started")
KNOWN_HEADERS = ("instrument", "settings", "started")


class LegacyCsvError(ValueError):
    """The file can't be read as a legacy logger CSV. `line` is 1-based, if known."""

    def __init__(self, message: str, line: int | None = None):
        super().__init__(f"line {line}: {message}" if line else message)
        self.line = line


@dataclass(frozen=True)
class Channel:
    name: str
    unit: str
    uncertainty: Decimal | None = None  # None means "not recorded", not zero


@dataclass(frozen=True)
class Reading:
    elapsed_s: Decimal
    t_local: datetime  # aware, America/Los_Angeles, keeps the source offset (N7)
    t_utc: datetime  # aware, UTC
    value: Decimal | None  # None for an empty cell; never replaced by 0


@dataclass
class LegacyRun:
    instrument_id: str
    settings_text: str | None
    started_local: datetime
    started_utc: datetime
    channels: list[Channel]
    readings: list[Reading]
    format_version: int = FORMAT_VERSION
    warnings: list[str] = field(default_factory=list)


def parse_legacy_csv(raw: bytes) -> LegacyRun:
    """Parse the bytes of a legacy logger CSV. Raises LegacyCsvError on bad input."""
    if not raw.strip():
        raise LegacyCsvError("file is empty")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LegacyCsvError("file is not UTF-8 text") from exc

    lines = text.splitlines()  # handles LF, CRLF and a mix of both
    warnings: list[str] = []

    headers, column_line_no = _read_headers(lines, warnings)
    missing = [name for name in REQUIRED_HEADERS if name not in headers]
    if missing:
        raise LegacyCsvError(f"missing header line(s): {', '.join('# ' + m for m in missing)}")
    if "settings" not in headers:
        warnings.append("no '# settings:' line; run configuration is unknown")

    started_local = _parse_local(headers["started"][0], headers["started"][1])
    if _is_ambiguous(started_local):
        warnings.append(
            "start time falls in the repeated hour when daylight saving ends; "
            "assumed daylight time (the earlier of the two)"
        )
    started_utc = started_local.astimezone(UTC)

    columns = _read_column_header(lines, column_line_no, warnings)

    readings: list[Reading] = []
    empty_cells = 0
    for line_no in range(column_line_no + 1, len(lines) + 1):
        line = lines[line_no - 1]
        if not line.strip():
            continue
        row = next(csv.reader([line]))
        if len(row) != len(columns):
            raise LegacyCsvError(f"expected {len(columns)} columns, found {len(row)}", line_no)
        cells = dict(zip(columns, (c.strip() for c in row), strict=True))

        elapsed = _parse_decimal(cells["elapsed_s"], "elapsed_s", line_no)
        if elapsed is None:
            raise LegacyCsvError("elapsed_s is empty", line_no)
        value = _parse_decimal(cells["volts"], "volts", line_no)
        if value is None:
            empty_cells += 1

        naive = _parse_naive(cells["timestamp"], line_no)
        if not _exists(naive.replace(tzinfo=SOURCE_TZ)):
            raise LegacyCsvError(f"{naive} does not exist in America/Los_Angeles", line_no)
        # float is used only to choose a side of the repeated hour, never for stored values
        t_local = _resolve_local(naive, started_utc + timedelta(seconds=float(elapsed)))
        readings.append(Reading(elapsed, t_local, t_local.astimezone(UTC), value))

    if not readings:
        raise LegacyCsvError("file has no readings")

    if any(a.elapsed_s >= b.elapsed_s for a, b in zip(readings, readings[1:])):
        readings.sort(key=lambda r: r.elapsed_s)
        warnings.append("readings were not in elapsed_s order; sorted by elapsed_s")
    for a, b in zip(readings, readings[1:]):
        if a.elapsed_s == b.elapsed_s:
            raise LegacyCsvError(f"two readings share elapsed_s {a.elapsed_s}")

    if empty_cells:
        warnings.append(f"{empty_cells} reading(s) have an empty volts cell (kept as missing)")
    warnings.append(NO_UNCERTAINTY_WARNING)

    return LegacyRun(
        instrument_id=headers["instrument"][0],
        settings_text=headers["settings"][0] if "settings" in headers else None,
        started_local=started_local,
        started_utc=started_utc,
        channels=[Channel(name="volts", unit="V")],
        readings=readings,
        warnings=warnings,
    )


def _read_headers(lines: list[str], warnings: list[str]) -> tuple[dict[str, tuple[str, int]], int]:
    """Read the leading '# key: value' lines. Returns them and the column-header line number."""
    headers: dict[str, tuple[str, int]] = {}
    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("#"):
            return headers, line_no
        key, sep, value = stripped.lstrip("#").partition(":")
        key = key.strip().lower()
        if not sep or not key:
            warnings.append(f"line {line_no}: comment line ignored")
        elif key in headers:
            raise LegacyCsvError(f"duplicate '# {key}:' line", line_no)
        elif key not in KNOWN_HEADERS:
            warnings.append(f"line {line_no}: unknown header '# {key}:' ignored")
        else:
            headers[key] = (value.strip(), line_no)
    raise LegacyCsvError("no column header line found")


def _read_column_header(lines: list[str], line_no: int, warnings: list[str]) -> list[str]:
    columns = [c.strip().lower() for c in next(csv.reader([lines[line_no - 1]]))]
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise LegacyCsvError(f"missing column(s): {', '.join(missing)}", line_no)
    if len(set(columns)) != len(columns):
        raise LegacyCsvError("duplicate column names", line_no)
    extra = [c for c in columns if c not in REQUIRED_COLUMNS + IGNORED_COLUMNS]
    if extra:
        warnings.append(f"unknown column(s) not imported: {', '.join(extra)}")
    return columns


def _parse_decimal(text: str, name: str, line_no: int) -> Decimal | None:
    if text == "":
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise LegacyCsvError(f"{name} is not a number: {text!r}", line_no) from None
    if not value.is_finite():
        raise LegacyCsvError(f"{name} is not a finite number: {text!r}", line_no)
    return value


def _parse_naive(text: str, line_no: int) -> datetime:
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        raise LegacyCsvError(f"timestamp is not ISO 8601: {text!r}", line_no) from None
    if value.tzinfo is not None:
        raise LegacyCsvError(f"timestamp has an offset; legacy files have none: {text!r}", line_no)
    return value


def _parse_local(text: str, line_no: int) -> datetime:
    naive = _parse_naive(text, line_no)
    local = naive.replace(tzinfo=SOURCE_TZ)
    if not _exists(local):
        raise LegacyCsvError(f"{text} does not exist in America/Los_Angeles", line_no)
    return local


def _resolve_local(naive: datetime, expected_utc: datetime) -> datetime:
    """Attach the source zone, using expected_utc to pick a side of the repeated hour."""
    candidates = [naive.replace(tzinfo=SOURCE_TZ, fold=f) for f in (0, 1)]
    return min(candidates, key=lambda dt: abs(dt.astimezone(UTC) - expected_utc))


def _is_ambiguous(local: datetime) -> bool:
    return local.replace(fold=0).utcoffset() != local.replace(fold=1).utcoffset() and _exists(
        local
    )


def _exists(local: datetime) -> bool:
    """False for times skipped when daylight saving starts (e.g. 02:30 in March)."""
    round_trip = local.astimezone(UTC).astimezone(SOURCE_TZ)
    return round_trip.replace(tzinfo=None) == local.replace(tzinfo=None)
