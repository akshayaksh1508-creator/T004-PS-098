
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from models import Pouring, PricedPouring
from dispute_service import register_dispute


class DisputeTests(unittest.TestCase):

    def make_priced_pouring(self):
        pouring = Pouring(
            pouring_id="P001",
            member_id="M001",
            pour_ts=datetime(2026, 11, 1, 6, 0),
            shift="AM",
            litres=Decimal("10.0"),
            fat_pct=Decimal("3.5"),
            snf_pct=Decimal("8.5"),
            temp_c=Decimal("8"),
            adulteration=False,
            can_id="CAN1",
        )

        return PricedPouring(
            pouring=pouring,
            fat_used=Decimal("3.5"),
            snf_used=Decimal("8.5"),
            chart_id="COW",
            chart_rate=Decimal("32.00"),
            snf_deduction=Decimal("0.00"),
            temp_deduction=Decimal("0.00"),
            price_per_litre=Decimal("32.00"),
            value=Decimal("320.00"),
            status="ACCEPTED",
            reject_reason="",
        )

    def test_dispute_within_24_hours_is_registered(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=12)

        dispute = register_dispute(
            "D001", priced, raised_at,
            new_fat="3.8",
        )

        self.assertEqual(dispute.dispute_id, "D001")
        self.assertEqual(dispute.pouring_id, "P001")
        self.assertEqual(dispute.new_fat, Decimal("3.8"))
        self.assertIsNone(dispute.new_snf)
        self.assertEqual(dispute.status, "REGISTERED")

    def test_dispute_at_exactly_24_hours_is_registered(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=24)

        dispute = register_dispute(
            "D002", priced, raised_at,
            new_snf="8.7",
        )

        self.assertEqual(dispute.status, "REGISTERED")

    def test_dispute_after_24_hours_is_rejected(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=24, seconds=1)

        with self.assertRaisesRegex(ValueError, "DISPUTE_TOO_LATE"):
            register_dispute(
                "D003", priced, raised_at,
                new_fat="3.8",
            )

    def test_dispute_before_pouring_is_rejected(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts - timedelta(minutes=1)

        with self.assertRaisesRegex(ValueError, "DISPUTE_BEFORE_POURING"):
            register_dispute(
                "D004", priced, raised_at,
                new_fat="3.8",
            )

    def test_missing_dispute_id_is_rejected(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=1)

        with self.assertRaisesRegex(ValueError, "INVALID_DISPUTE_ID"):
            register_dispute(
                "", priced, raised_at,
                new_fat="3.8",
            )

    def test_missing_retest_readings_are_rejected(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=1)

        with self.assertRaisesRegex(ValueError, "NO_RETEST_READING"):
            register_dispute("D005", priced, raised_at)

    def test_zero_fat_reading_is_rejected(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=1)

        with self.assertRaisesRegex(ValueError, "INVALID_RETEST_FAT"):
            register_dispute(
                "D006", priced, raised_at,
                new_fat="0",
            )

    def test_zero_snf_reading_is_rejected(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=1)

        with self.assertRaisesRegex(ValueError, "INVALID_RETEST_SNF"):
            register_dispute(
                "D007", priced, raised_at,
                new_snf="0",
            )

    def test_both_fat_and_snf_can_be_disputed(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=2)

        dispute = register_dispute(
            "D008", priced, raised_at,
            new_fat="3.8",
            new_snf="8.7",
        )

        self.assertEqual(dispute.new_fat, Decimal("3.8"))
        self.assertEqual(dispute.new_snf, Decimal("8.7"))


if __name__ == "__main__":
    unittest.main()
