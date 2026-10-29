"""Small standard-library tests for time validation and interval overlap logic."""
import unittest
from datetime import datetime
from shift_logic import parse_shift_times, intervals_overlap


class ShiftTimeTests(unittest.TestCase):
    def test_normal_shift(self):
        start, end = parse_shift_times("2026-10-28", "09:00", "13:00", False)
        self.assertEqual(start, "2026-10-28 09:00")
        self.assertEqual(end, "2026-10-28 13:00")

    def test_overnight_shift(self):
        start, end = parse_shift_times("2026-10-28", "22:00", "06:00", True)
        self.assertEqual(start, "2026-10-28 22:00")
        self.assertEqual(end, "2026-10-29 06:00")

    def test_invalid_same_day_time(self):
        with self.assertRaises(ValueError):
            parse_shift_times("2026-10-28", "13:00", "13:00", False)

    def test_overlap_is_detected(self):
        self.assertTrue(intervals_overlap(datetime(2026, 10, 28, 9), datetime(2026, 10, 28, 13),
                                datetime(2026, 10, 28, 12), datetime(2026, 10, 28, 15)))

    def test_adjacent_shifts_are_allowed(self):
        self.assertFalse(intervals_overlap(datetime(2026, 10, 28, 9), datetime(2026, 10, 28, 13),
                                 datetime(2026, 10, 28, 13), datetime(2026, 10, 28, 16)))

    def test_overnight_overlaps_next_morning(self):
        self.assertTrue(intervals_overlap(datetime(2026, 10, 28, 22), datetime(2026, 10, 29, 6),
                                datetime(2026, 10, 29, 5), datetime(2026, 10, 29, 8)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
