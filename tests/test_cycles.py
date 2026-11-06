
import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from cycle_service import (
    get_cycle_dates,
    get_payment_date,
    count_shifts,
    calculate_accepted_litres,
    calculate_loyalty_bonus,
    calculate_member_cycle_summary,
)


class CycleTests(unittest.TestCase):

    def make_result(
        self,
        member_id="M-010",
        day=11,
        shift="AM",
        litres="10.0",
        status="ACCEPTED",
    ):
        pouring = SimpleNamespace(
            member_id=member_id,
            pour_ts=datetime(2026, 1, day, 6, 0),
            shift=shift,
            litres=Decimal(litres),
        )

        return SimpleNamespace(
            pouring=pouring,
            status=status,
        )

    def test_first_cycle(self):
        self.assertEqual(
            get_cycle_dates(date(2026, 1, 5)),
            (date(2026, 1, 1), date(2026, 1, 10)),
        )

    def test_second_cycle(self):
        self.assertEqual(
            get_cycle_dates(date(2026, 1, 15)),
            (date(2026, 1, 11), date(2026, 1, 20)),
        )

    def test_third_cycle(self):
        self.assertEqual(
            get_cycle_dates(date(2026, 1, 25)),
            (date(2026, 1, 21), date(2026, 1, 31)),
        )

    def test_february_cycle(self):
        self.assertEqual(
            get_cycle_dates(date(2026, 2, 25)),
            (date(2026, 2, 21), date(2026, 2, 28)),
        )

    def test_leap_year_february_cycle(self):
        self.assertEqual(
            get_cycle_dates(date(2028, 2, 25)),
            (date(2028, 2, 21), date(2028, 2, 29)),
        )

    def test_december_cycle(self):
        self.assertEqual(
            get_cycle_dates(date(2026, 12, 25)),
            (date(2026, 12, 21), date(2026, 12, 31)),
        )

    def test_payment_date(self):
        self.assertEqual(
            get_payment_date(date(2026, 1, 20)),
            date(2026, 1, 23),
        )

    def test_payment_date_crosses_year(self):
        self.assertEqual(
            get_payment_date(date(2026, 12, 31)),
            date(2027, 1, 3),
        )

    def test_count_unique_shifts(self):
        results = [
            self.make_result(day=11, shift="AM"),
            self.make_result(day=11, shift="PM"),
            self.make_result(day=11, shift="AM"),
            self.make_result(day=12, shift="AM"),
        ]

        self.assertEqual(
            count_shifts(
                "M-010", results,
                date(2026, 1, 11), date(2026, 1, 20)
            ),
            3,
        )

    def test_rejected_pouring_not_counted(self):
        results = [
            self.make_result(day=11, status="ACCEPTED"),
            self.make_result(day=12, status="REJECTED"),
        ]

        self.assertEqual(
            count_shifts(
                "M-010", results,
                date(2026, 1, 11), date(2026, 1, 20)
            ),
            1,
        )

    def test_other_member_not_counted(self):
        results = [
            self.make_result(member_id="M-011"),
        ]

        self.assertEqual(
            count_shifts(
                "M-010", results,
                date(2026, 1, 11), date(2026, 1, 20)
            ),
            0,
        )

    def test_accepted_litres(self):
        results = [
            self.make_result(day=11, litres="10.0"),
            self.make_result(day=11, shift="PM", litres="8.5"),
            self.make_result(day=12, litres="5.0"),
            self.make_result(day=13, litres="4.0", status="REJECTED"),
        ]

        self.assertEqual(
            calculate_accepted_litres(
                "M-010", results,
                date(2026, 1, 11), date(2026, 1, 20)
            ),
            Decimal("23.5"),
        )

    def test_loyalty_bonus_exactly_15_shifts(self):
        self.assertEqual(
            calculate_loyalty_bonus(15, Decimal("108.5")),
            Decimal("54.25"),
        )

    def test_no_loyalty_bonus_for_14_shifts(self):
        self.assertEqual(
            calculate_loyalty_bonus(14, Decimal("108.5")),
            Decimal("0.00"),
        )

    def test_member_cycle_summary(self):
        results = [
            self.make_result(day=11, litres="50.0"),
            self.make_result(day=12, litres="58.5"),
        ]

        summary = calculate_member_cycle_summary(
            "M-010",
            results,
            date(2026, 1, 11),
            date(2026, 1, 20),
        )

        self.assertEqual(summary["shifts_poured"], 2)
        self.assertEqual(
            summary["accepted_litres"], Decimal("108.5")
        )
        self.assertEqual(
            summary["loyalty_bonus"], Decimal("0.00")
        )
        self.assertEqual(
            summary["payment_date"], date(2026, 1, 23)
        )


if __name__ == "__main__":
    unittest.main()
