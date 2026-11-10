"""Release gate: all five specs must be applied. Red until then."""
from datetime import date

from app import dates, report, settings, text


def test_spec_1_fmt_date_renamed():
    assert not hasattr(dates, "fmt_date"), "old name fmt_date must be gone"
    assert dates.format_date(date(2026, 2, 1)) == "2026-02-01"
    assert report.today_line() == "report " + dates.format_date(date.today())


def test_spec_2_timeout_45():
    assert settings.DEFAULT_TIMEOUT == 45


def test_spec_3_slugify():
    assert text.slugify("  Hello  World! ") == "hello-world"
    assert text.slugify("Big Data, 2026") == "big-data-2026"
    assert text.slugify("!!!") == ""


def test_spec_4_parse_us_dates():
    assert dates.parse("2026-04-17") == date(2026, 4, 17)
    assert dates.parse("04/17/2026") == date(2026, 4, 17)


def test_spec_5_debug_flag(monkeypatch):
    monkeypatch.setenv("DEBUG", "1")
    assert settings.debug() is True
    monkeypatch.setenv("DEBUG", "0")
    assert settings.debug() is False
    monkeypatch.delenv("DEBUG", raising=False)
    assert settings.debug() is False
