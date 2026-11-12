import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from models import Member, Pouring, PricedPouring
from dispute_service import register_dispute, process_retest


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

    def make_member(self):
        return Member(
            member_id="M001",
            society_id="S001",
            member_name="Test Member",
            cattle_type="COW",
        )


    def test_dispute_within_24_hours_is_registered(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=12)

        dispute = register_dispute(
            "D001", priced, raised_at, new_fat="3.8"
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
            "D002", priced, raised_at, new_snf="8.7"
        )

        self.assertEqual(dispute.status, "REGISTERED")

    def test_dispute_after_24_hours_is_rejected(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=24, seconds=1)

        with self.assertRaisesRegex(ValueError, "DISPUTE_TOO_LATE"):
            register_dispute("D003", priced, raised_at, new_fat="3.8")

    def test_dispute_before_pouring_is_rejected(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts - timedelta(minutes=1)

        with self.assertRaisesRegex(ValueError, "DISPUTE_BEFORE_POURING"):
            register_dispute("D004", priced, raised_at, new_fat="3.8")

    def test_missing_dispute_id_is_rejected(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=1)

        with self.assertRaisesRegex(ValueError, "INVALID_DISPUTE_ID"):
            register_dispute("", priced, raised_at, new_fat="3.8")

    def test_missing_retest_readings_are_rejected(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=1)

        with self.assertRaisesRegex(ValueError, "NO_RETEST_READING"):
            register_dispute("D005", priced, raised_at)

    def test_zero_fat_reading_is_rejected(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=1)

        with self.assertRaisesRegex(ValueError, "INVALID_RETEST_FAT"):
            register_dispute("D006", priced, raised_at, new_fat="0")

    def test_zero_snf_reading_is_rejected(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=1)

        with self.assertRaisesRegex(ValueError, "INVALID_RETEST_SNF"):
            register_dispute("D007", priced, raised_at, new_snf="0")

    def test_both_fat_and_snf_can_be_disputed(self):
        priced = self.make_priced_pouring()
        raised_at = priced.pouring.pour_ts + timedelta(hours=2)

        dispute = register_dispute(
            "D008", priced, raised_at,
            new_fat="3.8", new_snf="8.7"
        )

        self.assertEqual(dispute.new_fat, Decimal("3.8"))
        self.assertEqual(dispute.new_snf, Decimal("8.7"))


    def test_higher_fat_retest_updates_price(self):
        priced = self.make_priced_pouring()
        member = self.make_member()

        result = process_retest(
            {
                "test_id": "RT-001",
                "pouring_id": "P001",
                "dispute_ts": "2026-11-01 12:00:00",
                "parameter": "FAT",
                "retest_value": "3.8",
            },
            priced, member
        )

        self.assertEqual(result["status"], "ACCEPTED")
        self.assertEqual(result["original_value"], "3.5")
        self.assertEqual(result["value_used"], "3.8")
        self.assertEqual(priced.fat_used, Decimal("3.8"))
        self.assertEqual(priced.price_per_litre, Decimal("33.80"))
        self.assertEqual(priced.value, Decimal("338.00"))

    def test_lower_snf_retest_keeps_original_value(self):
        priced = self.make_priced_pouring()
        member = self.make_member()
        original_price = priced.price_per_litre

        result = process_retest(
            {
                "test_id": "RT-002",
                "pouring_id": "P001",
                "dispute_ts": "2026-11-01 12:00:00",
                "parameter": "SNF",
                "retest_value": "8.4",
            },
            priced, member
        )

        self.assertEqual(result["status"], "ACCEPTED")
        self.assertEqual(result["original_value"], "8.5")
        self.assertEqual(result["value_used"], "8.5")
        self.assertEqual(priced.snf_used, Decimal("8.5"))
        self.assertEqual(priced.price_per_litre, original_price)

    def test_retest_after_24_hours_is_rejected(self):
        priced = self.make_priced_pouring()
        member = self.make_member()
        original_price = priced.price_per_litre

        result = process_retest(
            {
                "test_id": "RT-003",
                "pouring_id": "P001",
                "dispute_ts": "2026-11-02 06:00:01",
                "parameter": "FAT",
                "retest_value": "4.0",
            },
            priced, member
        )

        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["value_used"], "3.5")
        self.assertEqual(priced.fat_used, Decimal("3.5"))
        self.assertEqual(priced.price_per_litre, original_price)

    def test_retest_at_exactly_24_hours_is_accepted(self):
        priced = self.make_priced_pouring()
        member = self.make_member()

        result = process_retest(
            {
                "test_id": "RT-004",
                "pouring_id": "P001",
                "dispute_ts": "2026-11-02 06:00:00",
                "parameter": "FAT",
                "retest_value": "3.8",
            },
            priced, member
        )

        self.assertEqual(result["status"], "ACCEPTED")
        self.assertEqual(result["value_used"], "3.8")

    def test_retest_before_pouring_is_rejected(self):
        priced = self.make_priced_pouring()
        member = self.make_member()

        result = process_retest(
            {
                "test_id": "RT-005",
                "pouring_id": "P001",
                "dispute_ts": "2026-11-01 05:59:59",
                "parameter": "FAT",
                "retest_value": "4.0",
            },
            priced, member
        )

        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["value_used"], "3.5")

    def test_higher_snf_retest_updates_price(self):
        priced = self.make_priced_pouring()
        member = self.make_member()

        result = process_retest(
            {
                "test_id": "RT-006",
                "pouring_id": "P001",
                "dispute_ts": "2026-11-01 12:00:00",
                "parameter": "SNF",
                "retest_value": "8.7",
            },
            priced, member
        )

        self.assertEqual(result["status"], "ACCEPTED")
        self.assertEqual(priced.snf_used, Decimal("8.7"))
        self.assertEqual(priced.price_per_litre, Decimal("32.60"))
        self.assertEqual(priced.value, Decimal("326.00"))

    def test_lower_fat_retest_keeps_original_value(self):
        priced = self.make_priced_pouring()
        member = self.make_member()
        original_price = priced.price_per_litre

        result = process_retest(
            {
                "test_id": "RT-007",
                "pouring_id": "P001",
                "dispute_ts": "2026-11-01 12:00:00",
                "parameter": "FAT",
                "retest_value": "3.2",
            },
            priced, member
        )

        self.assertEqual(result["status"], "ACCEPTED")
        self.assertEqual(result["value_used"], "3.5")
        self.assertEqual(priced.fat_used, Decimal("3.5"))
        self.assertEqual(priced.price_per_litre, original_price)

    def test_invalid_retest_parameter_is_rejected(self):
        priced = self.make_priced_pouring()
        member = self.make_member()

        with self.assertRaisesRegex(ValueError, "INVALID_RETEST_PARAMETER"):
            process_retest(
                {
                    "test_id": "RT-008",
                    "pouring_id": "P001",
                    "dispute_ts": "2026-11-01 12:00:00",
                    "parameter": "TEMP",
                    "retest_value": "9",
                },
                priced, member
            )


if __name__ == "__main__":
    unittest.main()
