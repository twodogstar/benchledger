"""Legacy logger CSV parser (M8, R1)."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from benchledger.importers.legacy_csv import (
    NO_UNCERTAINTY_WARNING,
    LegacyCsvError,
    parse_legacy_csv,
)

FIXTURE = Path(__file__).parent / "fixtures" / "adr1399_20261031_231722.csv"

HEADER = (
    "# instrument: HEWLETT-PACKARD,34401A,0,4-1-1\n"
    "# settings: DCV 10V range, NPLC 100\n"
    "# started: {started}\n"
    "timestamp,elapsed_s,volts,delta_ppm\n"
)


def make(rows: list[str], started: str = "2026-10-31T23:00:00") -> bytes:
    return (HEADER.format(started=started) + "\n".join(rows) + "\n").encode()


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


# --- the real Oct 31 file -----------------------------------------------------


@pytest.fixture(scope="module")
def real_run():
    return parse_legacy_csv(FIXTURE.read_bytes())


def test_real_file_header(real_run):
    assert real_run.instrument_id == "HEWLETT-PACKARD,34401A,0,4-1-1"
    assert real_run.settings_text == (
        "DCV 10V range, NPLC 100, autozero ON, Zin >10GOhm, interval 0.0s"
    )
    assert real_run.format_version == 0
    # 23:17:23 PDT (UTC-7) is 06:17:23 UTC the next day
    assert real_run.started_utc == utc(2026, 11, 1, 6, 17, 23)


def test_real_file_readings(real_run):
    assert len(real_run.readings) == 1224
    first, last = real_run.readings[0], real_run.readings[-1]
    assert first.elapsed_s == Decimal("3.4")
    assert first.t_utc == utc(2026, 11, 1, 6, 17, 26)
    assert last.elapsed_s == Decimal("4112.0")
    assert last.t_utc == utc(2026, 11, 1, 7, 25, 55)


def test_real_file_keeps_full_precision(real_run):
    first = real_run.readings[0]
    assert isinstance(first.value, Decimal)
    assert str(first.value) == "7.05483570"  # trailing zero kept: 8 decimal places as logged


def test_real_file_unit_and_uncertainty(real_run):
    (channel,) = real_run.channels
    assert (channel.name, channel.unit, channel.uncertainty) == ("volts", "V", None)
    assert NO_UNCERTAINTY_WARNING in real_run.warnings


def test_real_file_keeps_source_offset(real_run):
    assert real_run.readings[0].t_local.utcoffset().total_seconds() == -7 * 3600


# --- time handling ------------------------------------------------------------


def test_repeated_hour_resolved_by_elapsed():
    # Daylight saving ends 2026-11-01 02:00 PDT -> 01:00 PST; 01:00-02:00 happens twice.
    raw = make(
        [
            # started 00:30 PDT = 07:30Z
            "2026-11-01T01:30:00,3600.0,7.0,",  # first 01:30, PDT = 08:30Z
            "2026-11-01T01:59:59,5399.0,7.0,",  # PDT = 08:59:59Z
            "2026-11-01T01:00:00,5400.0,7.0,",  # second 01:00, PST = 09:00Z
            "2026-11-01T01:30:00,7200.0,7.0,",  # second 01:30, PST = 09:30Z
            "2026-11-01T02:10:00,9600.0,7.0,",  # PST = 10:10Z
        ],
        started="2026-11-01T00:30:00",
    )
    run = parse_legacy_csv(raw)
    assert [r.t_utc for r in run.readings] == [
        utc(2026, 11, 1, 8, 30),
        utc(2026, 11, 1, 8, 59, 59),
        utc(2026, 11, 1, 9, 0),
        utc(2026, 11, 1, 9, 30),
        utc(2026, 11, 1, 10, 10),
    ]
    utc_times = [r.t_utc for r in run.readings]
    assert utc_times == sorted(utc_times)


def test_rows_sorted_by_elapsed_with_warning():
    raw = make(["2026-10-31T23:00:10,10.0,7.1,", "2026-10-31T23:00:05,5.0,7.0,"])
    run = parse_legacy_csv(raw)
    assert [r.elapsed_s for r in run.readings] == [Decimal("5.0"), Decimal("10.0")]
    assert any("sorted by elapsed_s" in w for w in run.warnings)


def test_skipped_local_time_is_rejected():
    # 2027-03-14 02:30 does not exist in Los Angeles (clocks jump 02:00 -> 03:00).
    raw = make(["2027-03-14T02:30:00,5.0,7.0,"], started="2027-03-14T01:59:00")
    with pytest.raises(LegacyCsvError, match="does not exist"):
        parse_legacy_csv(raw)


# --- line endings and missing values ------------------------------------------


def test_mixed_line_endings():
    text = make(["2026-10-31T23:00:05,5.0,7.0,+0.000", "2026-10-31T23:00:10,10.0,7.1,"]).decode()
    head, _, body = text.partition("timestamp")
    mixed = (head + "timestamp" + body.replace("\n", "\r\n")).encode()
    assert len(parse_legacy_csv(mixed).readings) == 2


def test_empty_value_kept_as_missing():
    run = parse_legacy_csv(make(["2026-10-31T23:00:05,5.0,,", "2026-10-31T23:00:10,10.0,7.1,"]))
    assert run.readings[0].value is None  # never turned into 0
    assert any("empty volts cell" in w for w in run.warnings)


def test_missing_settings_is_a_warning():
    text = make(["2026-10-31T23:00:05,5.0,7.0,"]).decode()
    text = "\n".join(ln for ln in text.split("\n") if not ln.startswith("# settings:"))
    run = parse_legacy_csv(text.encode())
    assert run.settings_text is None
    assert any("settings" in w for w in run.warnings)


# --- bad input ----------------------------------------------------------------


@pytest.mark.parametrize("raw", [b"", b"  \n\n"])
def test_empty_file(raw):
    with pytest.raises(LegacyCsvError, match="empty"):
        parse_legacy_csv(raw)


def test_header_only_file():
    with pytest.raises(LegacyCsvError, match="no readings"):
        parse_legacy_csv(make([]))


@pytest.mark.parametrize("line", ["# instrument:", "# started:"])
def test_missing_required_header(line):
    text = make(["2026-10-31T23:00:05,5.0,7.0,"]).decode()
    text = "\n".join(ln for ln in text.split("\n") if not ln.startswith(line))
    with pytest.raises(LegacyCsvError, match="missing header"):
        parse_legacy_csv(text.encode())


def test_missing_column():
    raw = make(["2026-10-31T23:00:05,5.0,"]).decode().replace(",volts,", ",vlots,").encode()
    with pytest.raises(LegacyCsvError, match="missing column"):
        parse_legacy_csv(raw)


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("2026-10-31T23:00:05,5.0,7.0x,", "volts is not a number"),
        ("2026-10-31T23:00:05,5.0,nan,", "not a finite number"),
        ("2026-10-31T23:00:05,,7.0,", "elapsed_s is empty"),
        ("yesterday,5.0,7.0,", "not ISO 8601"),
        ("2026-10-31T23:00:05,5.0,7.0", "expected 4 columns"),
    ],
)
def test_bad_row_reports_line(row, message):
    with pytest.raises(LegacyCsvError, match=message) as exc:
        parse_legacy_csv(make(["2026-10-31T23:00:00,1.0,7.0,", row]))
    assert exc.value.line == 6


def test_duplicate_elapsed_rejected():
    raw = make(["2026-10-31T23:00:05,5.0,7.0,", "2026-10-31T23:00:05,5.0,7.1,"])
    with pytest.raises(LegacyCsvError, match="share elapsed_s"):
        parse_legacy_csv(raw)


def test_not_utf8():
    with pytest.raises(LegacyCsvError, match="UTF-8"):
        parse_legacy_csv(b"\xff\xfe# instrument: x\n")
