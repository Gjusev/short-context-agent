import unittest
from datetime import timedelta

from app.dates.parse import parse_date


class ScheduleTests(unittest.TestCase):
    def test_offset_input_is_not_rewritten(self):
        self.assertEqual(parse_date("2024-07-01T09:00+02:00").utcoffset(), timedelta(hours=2))


if __name__ == "__main__":
    unittest.main()
