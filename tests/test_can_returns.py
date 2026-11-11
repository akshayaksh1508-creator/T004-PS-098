import unittest
from datetime import date, datetime
from decimal import Decimal

from can_return_service import apply_can_rejection
from models import CanRejection, Member, Pouring
from pouring_service import process_pourings


class CanReturnTests(unittest.TestCase):

    def make_results(self):
        member = Member("M001", "S001", "Ravi", "COW")

        pourings = [
            Pouring(
                "P001", "M001", datetime(2026, 1, 12, 6, 0, 0),
                "AM", Decimal("10.0"), Decimal("3.5"),
                Decimal("8.5"), Decimal("8"), False, "CAN1",
            ),
            Pouring(
                "P002", "M001", datetime(2026, 1, 12, 18, 0, 0),
                "PM", Decimal("5.0"), Decimal("3.5"),
                Decimal("8.5"), Decimal("8"), False, "CAN2",
            ),
        ]

        return member, process_pourings(
            pourings, {"M001": member}
        )

    def test_rejection_reverses_can_pourings_at_50_percent(self):
        member, results = self.make_results()

        rejection = CanRejection(
            "CR-01", "CAN1",
            datetime(2026, 1, 12, 11, 20, 0), "SOUR",
        )

        info = apply_can_rejection(
            rejection, results, {"M001": member}
        )

        self.assertEqual(
            results[0].sour_reversal, Decimal("160.00")
        )
        self.assertEqual(
            results[1].sour_reversal, Decimal("0.00")
        )
        self.assertEqual(info["society_id"], "S001")
        self.assertEqual(
            info["rejected_date"], date(2026, 1, 12)
        )
        self.assertEqual(
            info["reversed_value"], Decimal("160.00")
        )

    def test_unknown_can_returns_none(self):
        member, results = self.make_results()

        rejection = CanRejection(
            "CR-02", "CAN9",
            datetime(2026, 1, 12, 11, 20, 0), "SOUR",
        )

        info = apply_can_rejection(
            rejection, results, {"M001": member}
        )

        self.assertIsNone(info)
        self.assertEqual(
            results[0].sour_reversal, Decimal("0.00")
        )

    def test_rejected_pouring_in_can_is_not_reversed(self):
        member = Member("M001", "S001", "Ravi", "COW")

        pourings = [
            Pouring(
                "P001", "M001", datetime(2026, 1, 12, 6, 0, 0),
                "AM", Decimal("10.0"), Decimal("2.9"),
                Decimal("8.5"), Decimal("8"), False, "CAN1",
            ),
        ]

        results = process_pourings(
            pourings, {"M001": member}
        )

        rejection = CanRejection(
            "CR-01", "CAN1",
            datetime(2026, 1, 12, 11, 20, 0), "SOUR",
        )

        info = apply_can_rejection(
            rejection, results, {"M001": member}
        )

        self.assertIsNone(info)

    def test_invalid_rejection_id_raises(self):
        _, results = self.make_results()

        rejection = CanRejection(
            "", "CAN1",
            datetime(2026, 1, 12, 11, 20, 0), "SOUR",
        )

        with self.assertRaises(ValueError):
            apply_can_rejection(rejection, results, {})

    def test_invalid_can_id_raises(self):
        _, results = self.make_results()

        rejection = CanRejection(
            "CR-01", "",
            datetime(2026, 1, 12, 11, 20, 0), "SOUR",
        )

        with self.assertRaises(ValueError):
            apply_can_rejection(rejection, results, {})

    def test_invalid_timestamp_raises(self):
        _, results = self.make_results()

        rejection = CanRejection(
            "CR-01", "CAN1", "not-a-timestamp", "SOUR"
        )

        with self.assertRaises(ValueError):
            apply_can_rejection(rejection, results, {})


if __name__ == "__main__":
    unittest.main()
