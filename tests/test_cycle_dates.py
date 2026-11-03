import unittest
from datetime import date

from app.cycle_dates import cycle_dates, cycle_number, payment_date


class CycleDateTests(unittest.TestCase):
    def test_cycle_numbers(self):
        self.assertEqual(cycle_number(1), 1)
        self.assertEqual(cycle_number(10), 1)
        self.assertEqual(cycle_number(11), 2)
        self.assertEqual(cycle_number(20), 2)
        self.assertEqual(cycle_number(21), 3)

    def test_february_cycle_ends_on_february_28(self):
        self.assertEqual(
            cycle_dates(2026, 2, 3),
            (date(2026, 2, 21), date(2026, 2, 28)),
        )

    def test_payment_is_three_days_after_close(self):
        self.assertEqual(payment_date(2026, 2, 3), date(2026, 3, 3))


if __name__ == "__main__":
    unittest.main()
