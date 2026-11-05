import unittest
from datetime import date, timedelta
from decimal import Decimal

from models import Member, Pouring
from pouring_service import process_pouring, process_pourings


class PouringTests(unittest.TestCase):

    def make_member(self, cattle_type="COW"):
        return Member("M001", "S001", "Ravi", cattle_type)

    def make_pouring(self, **values):
        defaults = {
            "pouring_id": "P001",
            "member_id": "M001",
            "society_id": "S001",
            "date": date(2026, 11, 1),
            "shift": "AM",
            "litres": Decimal("10.0"),
            "fat": Decimal("3.5"),
            "snf": Decimal("8.5"),
            "temperature": Decimal("8"),
            "adulteration": False,
            "can_id": "CAN1",
        }
        defaults.update(values)
        return Pouring(**defaults)

    def test_cow_base_price(self):
        result = process_pouring(self.make_pouring(), self.make_member())

        self.assertTrue(result.accepted)
        self.assertEqual(result.milk_type, "COW")
        self.assertEqual(result.price_per_litre, Decimal("32.00"))
        self.assertEqual(result.value, Decimal("320.00"))

    def test_low_snf_penalty(self):
        result = process_pouring(
            self.make_pouring(snf=Decimal("7.9")),
            self.make_member(),
        )

        self.assertEqual(result.quality_adjustment, Decimal("-1.00"))
        self.assertEqual(result.price_per_litre, Decimal("29.20"))

    def test_high_temperature_penalty(self):
        result = process_pouring(
            self.make_pouring(temperature=Decimal("10.5")),
            self.make_member(),
        )

        self.assertEqual(result.quality_adjustment, Decimal("-0.50"))
        self.assertEqual(result.price_per_litre, Decimal("31.50"))

    def test_snf_and_temperature_penalties_together(self):
        result = process_pouring(
            self.make_pouring(
                snf=Decimal("7.9"),
                temperature=Decimal("11"),
            ),
            self.make_member(),
        )

        self.assertEqual(result.quality_adjustment, Decimal("-1.50"))
        self.assertEqual(result.price_per_litre, Decimal("28.70"))

    def test_snf_boundary_has_no_penalty(self):
        result = process_pouring(
            self.make_pouring(snf=Decimal("8.0")),
            self.make_member(),
        )

        self.assertEqual(result.quality_adjustment, Decimal("0.00"))

    def test_temperature_boundary_has_no_penalty(self):
        result = process_pouring(
            self.make_pouring(temperature=Decimal("10")),
            self.make_member(),
        )

        self.assertEqual(result.quality_adjustment, Decimal("0.00"))

    def test_buffalo_low_snf_penalty(self):
        result = process_pouring(
            self.make_pouring(fat=Decimal("6.0"), snf=Decimal("8.4")),
            self.make_member(cattle_type="BUFFALO"),
        )

        self.assertEqual(result.milk_type, "BUFFALO")
        self.assertEqual(result.quality_adjustment, Decimal("-1.00"))
        self.assertEqual(result.price_per_litre, Decimal("45.80"))

    def test_mixed_uses_cow_chart(self):
        result = process_pouring(
            self.make_pouring(fat=Decimal("5.5")),
            self.make_member(cattle_type="MIXED"),
        )

        self.assertTrue(result.accepted)
        self.assertEqual(result.milk_type, "COW")
        self.assertEqual(result.price_per_litre, Decimal("44.00"))

    def test_fat_below_three_is_rejected(self):
        result = process_pouring(
            self.make_pouring(fat=Decimal("2.9")),
            self.make_member(),
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.rejection_reason, "FAT_TOO_LOW")

    def test_adulteration_rejects_and_suspends(self):
        member = self.make_member()
        pouring = self.make_pouring(adulteration=True)

        result = process_pouring(pouring, member)

        self.assertFalse(result.accepted)
        self.assertEqual(result.rejection_reason, "ADULTERATION_POSITIVE")
        self.assertEqual(
            member.suspended_until,
            pouring.date + timedelta(days=7),
        )

    def test_suspended_member_is_rejected(self):
        member = self.make_member()
        member.suspended_until = date(2026, 11, 7)

        result = process_pouring(
            self.make_pouring(date=date(2026, 11, 5)),
            member,
        )

        self.assertFalse(result.accepted)
        self.assertEqual(result.rejection_reason, "MEMBER_SUSPENDED")

    def test_inactive_member_is_rejected(self):
        member = self.make_member()
        member.status = "EXITED"

        result = process_pouring(self.make_pouring(), member)

        self.assertFalse(result.accepted)
        self.assertEqual(result.rejection_reason, "MEMBER_INACTIVE")

    def test_value_is_rounded_to_paisa(self):
        result = process_pouring(
            self.make_pouring(
                litres=Decimal("10.5"),
                fat=Decimal("3.56"),
                snf=Decimal("8.53"),
            ),
            self.make_member(),
        )

        self.assertEqual(result.price_per_litre, Decimal("32.45"))
        self.assertEqual(result.value, Decimal("340.73"))


class ProcessPouringsTests(unittest.TestCase):

    def make_member(self):
        return Member("M001", "S001", "Ravi", "COW")

    def make_pouring(self, pouring_id="P001", **values):
        defaults = {
            "member_id": "M001",
            "society_id": "S001",
            "date": date(2026, 11, 1),
            "shift": "AM",
            "litres": Decimal("10.0"),
            "fat": Decimal("3.5"),
            "snf": Decimal("8.5"),
            "temperature": Decimal("8"),
            "adulteration": False,
            "can_id": "CAN1",
        }
        defaults.update(values)
        return Pouring(pouring_id, **defaults)

    def test_invalid_shift_is_rejected(self):
        results = process_pourings(
            [self.make_pouring(shift="NIGHT")],
            {"M001": self.make_member()},
        )

        self.assertFalse(results[0].accepted)
        self.assertEqual(results[0].rejection_reason, "INVALID_SHIFT")

    def test_invalid_litres_is_rejected(self):
        results = process_pourings(
            [self.make_pouring(litres=Decimal("10.15"))],
            {"M001": self.make_member()},
        )

        self.assertFalse(results[0].accepted)
        self.assertEqual(results[0].rejection_reason, "INVALID_LITRES")

    def test_unknown_member_is_rejected(self):
        results = process_pourings(
            [self.make_pouring(member_id="M999")],
            {"M001": self.make_member()},
        )

        self.assertFalse(results[0].accepted)
        self.assertEqual(results[0].rejection_reason, "UNKNOWN_MEMBER")

    def test_duplicate_pouring_id_is_rejected(self):
        pouring = self.make_pouring()

        results = process_pourings(
            [pouring, pouring],
            {"M001": self.make_member()},
        )

        self.assertTrue(results[0].accepted)
        self.assertFalse(results[1].accepted)
        self.assertEqual(results[1].rejection_reason, "DUPLICATE_POURING")


if __name__ == "__main__":
    unittest.main()
