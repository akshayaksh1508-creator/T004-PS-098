import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from models import CanRejection, Member, Society
from society_service import calculate_society_settlement


def make_result(
    member_id="M001",
    day=11,
    litres="10.0",
    value="320.00",
    can_id="CAN1",
    sour_reversal="0.00",
    status="ACCEPTED",
):
    pouring = SimpleNamespace(
        member_id=member_id,
        can_id=can_id,
        pour_ts=datetime(2026, 1, day, 6, 0),
        litres=Decimal(litres),
    )

    return SimpleNamespace(
        pouring=pouring,
        status=status,
        value=Decimal(value),
        sour_reversal=Decimal(sour_reversal),
    )


def make_society(distance_km="15.0"):
    return Society(
        society_id="S001",
        union_id="U1",
        society_name="Hirisave Society",
        village="Hirisave",
        distance_km=Decimal(distance_km),
        commission_pct=Decimal("2.50"),
    )


def make_members():
    return {
        "M001": Member("M001", "S001", "Ravi", "COW"),
        "M002": Member("M002", "S002", "Sita", "COW"),
    }


def make_rejection(rejection_id, can_id, day, hour=11, minute=20):
    return CanRejection(
        rejection_id,
        can_id,
        datetime(2026, 1, day, hour, minute, 0),
        "SOUR",
    )


class SocietySettlementTests(unittest.TestCase):

    def test_commission_handling_and_no_subsidy_at_15_km(self):
        results = [
            make_result(day=11, litres="10.0", value="320.00"),
            make_result(day=12, litres="15.0", value="480.00"),
        ]

        settlement = calculate_society_settlement(
            make_society(),
            make_members(),
            results,
            [],
            date(2026, 1, 11),
            date(2026, 1, 20),
        )

        self.assertEqual(
            settlement["accepted_litres"], Decimal("25.0")
        )
        self.assertEqual(
            settlement["pouring_value"], Decimal("800.00")
        )
        self.assertEqual(
            settlement["commission"], Decimal("20.00")
        )
        self.assertEqual(
            settlement["handling"], Decimal("5.00")
        )
        self.assertEqual(
            settlement["transport_subsidy"], Decimal("0.00")
        )
        self.assertEqual(
            settlement["commission_forfeited"], False
        )
        self.assertEqual(
            settlement["net_settlement"], Decimal("25.00")
        )

    def test_transport_subsidy_above_15_km(self):
        results = [
            make_result(day=11, litres="10.0", value="320.00"),
        ]

        settlement = calculate_society_settlement(
            make_society(distance_km="22.4"),
            make_members(),
            results,
            [],
            date(2026, 1, 11),
            date(2026, 1, 20),
        )

        self.assertEqual(
            settlement["transport_subsidy"], Decimal("1.50")
        )
        self.assertEqual(
            settlement["net_settlement"],
            Decimal("8.00") + Decimal("2.00")
            + Decimal("1.50"),
        )

    def test_sour_milk_share_reduces_net(self):
        results = [
            make_result(day=11, value="320.00", sour_reversal="160.00"),
        ]

        settlement = calculate_society_settlement(
            make_society(distance_km="22.4"),
            make_members(),
            results,
            [],
            date(2026, 1, 11),
            date(2026, 1, 20),
        )

        self.assertEqual(
            settlement["sour_milk_share"], Decimal("160.00")
        )
        self.assertEqual(
            settlement["net_settlement"], Decimal("8.00")
            + Decimal("2.00") + Decimal("1.50")
            - Decimal("160.00"),
        )

    def test_outside_cycle_pourings_are_excluded(self):
        results = [
            make_result(day=9, litres="10.0", value="320.00"),
            make_result(day=11, litres="10.0", value="320.00"),
        ]

        settlement = calculate_society_settlement(
            make_society(),
            make_members(),
            results,
            [],
            date(2026, 1, 11),
            date(2026, 1, 20),
        )

        self.assertEqual(
            settlement["accepted_litres"], Decimal("10.0")
        )
        self.assertEqual(
            settlement["pouring_value"], Decimal("320.00")
        )

    def test_three_distinct_return_days_forfeit_commission(self):
        results = [
            make_result(day=12, can_id="C1"),
            make_result(day=15, can_id="C2"),
            make_result(day=20, can_id="C3"),
        ]

        rejections = [
            make_rejection("CR-01", "C1", 12),
            make_rejection("CR-02", "C2", 15),
            # 23:59 on the third distinct day still counts.
            make_rejection(
                "CR-03", "C3", 20, hour=23, minute=59
            ),
        ]

        settlement = calculate_society_settlement(
            make_society(distance_km="22.4"),
            make_members(),
            results,
            rejections,
            date(2026, 1, 11),
            date(2026, 1, 20),
        )

        self.assertTrue(settlement["commission_forfeited"])
        self.assertEqual(
            settlement["commission"], Decimal("0.00")
        )
        self.assertEqual(
            settlement["handling"], Decimal("0.00")
        )
        # Transport subsidy stays even when commission is forfeited.
        self.assertEqual(
            settlement["transport_subsidy"], Decimal("4.50")
        )

    def test_two_distinct_return_days_keep_commission(self):
        results = [
            make_result(day=12, can_id="C1"),
            make_result(day=12, can_id="C2"),
            make_result(day=15, can_id="C3"),
        ]

        # Two cans rejected on the same day count as one day.
        rejections = [
            make_rejection("CR-01", "C1", 12),
            make_rejection("CR-02", "C2", 12),
            make_rejection("CR-03", "C3", 15),
        ]

        settlement = calculate_society_settlement(
            make_society(),
            make_members(),
            results,
            rejections,
            date(2026, 1, 11),
            date(2026, 1, 20),
        )

        self.assertFalse(settlement["commission_forfeited"])
        self.assertEqual(
            settlement["commission"], Decimal("24.00")
        )
        self.assertEqual(
            settlement["handling"], Decimal("6.00")
        )

    def test_rejection_outside_cycle_is_not_counted(self):
        results = [
            make_result(day=12, can_id="C1"),
            make_result(day=15, can_id="C2"),
            make_result(day=21, can_id="C3"),
        ]

        rejections = [
            make_rejection("CR-01", "C1", 12),
            make_rejection("CR-02", "C2", 15),
            make_rejection("CR-03", "C3", 21),
        ]

        settlement = calculate_society_settlement(
            make_society(),
            make_members(),
            results,
            rejections,
            date(2026, 1, 11),
            date(2026, 1, 20),
        )

        self.assertFalse(settlement["commission_forfeited"])
        self.assertEqual(settlement["return_days"], 2)

    def test_other_society_rejection_is_not_counted(self):
        results = [
            make_result(
                member_id="M002", day=12, can_id="C1"
            ),
        ]

        rejections = [
            make_rejection("CR-01", "C1", 12),
        ]

        settlement = calculate_society_settlement(
            make_society(),
            make_members(),
            results,
            rejections,
            date(2026, 1, 11),
            date(2026, 1, 20),
        )

        self.assertEqual(settlement["return_days"], 0)
        self.assertEqual(
            settlement["accepted_litres"], Decimal("0.0")
        )


if __name__ == "__main__":
    unittest.main()
