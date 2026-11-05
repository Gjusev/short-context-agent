import unittest
from datetime import datetime, timezone, timedelta

from app.dates.parse import parse_date


class ParseDateTests(unittest.TestCase):
    def test_parse_date_naive_is_utc(self):
        self.assertEqual(parse_date("2024-07-10T02:30"),
                         datetime(2024, 7, 10, 2, 30, tzinfo=timezone.utc))

    def test_parse_date_keeps_explicit_offset(self):
        dt = parse_date("2024-07-10T02:30+01:00")
        self.assertEqual(dt.utcoffset(), timedelta(hours=1))


if __name__ == "__main__":
    unittest.main()
