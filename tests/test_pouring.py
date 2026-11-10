
import unittest
from datetime import datetime, timedelta
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
            "pour_ts": datetime(2026, 11, 1, 6, 0, 0),
            "shift": "AM",
            "litres": Decimal("10.0"),
            "fat_pct": Decimal("3.5"),
            "snf_pct": Decimal("8.5"),
            "temp_c": Decimal("8"),
            "adulteration": False,
            "can_id": "CAN1",
        }
        defaults.update(values)
        return Pouring(**defaults)

    def test_cow_base_price(self):
        result = process_pouring(self.make_pouring(), self.make_member())

        self.assertEqual(result.status, "ACCEPTED")
        self.assertEqual(result.chart_id, "COW")
        self.assertEqual(result.chart_rate, Decimal("32.00"))
        self.assertEqual(result.price_per_litre, Decimal("32.00"))
        self.assertEqual(result.value, Decimal("320.00"))

    def test_low_snf_penalty(self):
        result = process_pouring(
            self.make_pouring(snf_pct=Decimal("7.9")),
            self.make_member(),
        )

        self.assertEqual(result.chart_rate, Decimal("30.20"))
        self.assertEqual(result.snf_deduction, Decimal("1.00"))
        self.assertEqual(result.price_per_litre, Decimal("29.20"))

    def test_high_temperature_penalty(self):
        result = process_pouring(
            self.make_pouring(temp_c=Decimal("10.5")),
            self.make_member(),
        )

        self.assertEqual(result.temp_deduction, Decimal("0.50"))
        self.assertEqual(result.price_per_litre, Decimal("31.50"))

    def test_snf_and_temperature_penalties_together(self):
        result = process_pouring(
            self.make_pouring(
                snf_pct=Decimal("7.9"),
                temp_c=Decimal("11"),
            ),
            self.make_member(),
        )

        self.assertEqual(result.snf_deduction, Decimal("1.00"))
        self.assertEqual(result.temp_deduction, Decimal("0.50"))
        self.assertEqual(result.price_per_litre, Decimal("28.70"))

    def test_snf_boundary_has_no_penalty(self):
        result = process_pouring(
            self.make_pouring(snf_pct=Decimal("8.0")),
            self.make_member(),
        )

        self.assertEqual(result.snf_deduction, Decimal("0.00"))

    def test_temperature_boundary_has_no_penalty(self):
        result = process_pouring(
            self.make_pouring(temp_c=Decimal("10")),
            self.make_member(),
        )

        self.assertEqual(result.temp_deduction, Decimal("0.00"))

    def test_buffalo_low_snf_penalty(self):
        result = process_pouring(
            self.make_pouring(
                fat_pct=Decimal("6.0"), snf_pct=Decimal("8.4")
            ),
            self.make_member(cattle_type="BUFFALO"),
        )

        self.assertEqual(result.chart_id, "BUFFALO")
        self.assertEqual(result.chart_rate, Decimal("46.80"))
        self.assertEqual(result.snf_deduction, Decimal("1.00"))
        self.assertEqual(result.price_per_litre, Decimal("45.80"))

    def test_mixed_uses_cow_chart(self):
        result = process_pouring(
            self.make_pouring(fat_pct=Decimal("5.5")),
            self.make_member(cattle_type="MIXED"),
        )

        self.assertEqual(result.status, "ACCEPTED")
        self.assertEqual(result.chart_id, "COW")
        self.assertEqual(result.chart_rate, Decimal("44.00"))

    def test_fat_below_three_is_rejected(self):
        result = process_pouring(
            self.make_pouring(fat_pct=Decimal("2.9")),
            self.make_member(),
        )

        self.assertEqual(result.status, "REJECTED")
        self.assertEqual(result.reject_reason, "FAT_TOO_LOW")

    def test_adulteration_rejects_and_suspends(self):
        member = self.make_member()
        pouring = self.make_pouring(adulteration=True)

        result = process_pouring(pouring, member)

        self.assertEqual(result.status, "REJECTED")
        self.assertEqual(
            result.reject_reason, "ADULTERATION_POSITIVE"
        )
        self.assertEqual(
            member.suspended_until,
            pouring.pour_ts.date() + timedelta(days=7),
        )

    def test_adulteration_takes_priority_over_low_fat(self):
        member = self.make_member()
        pouring = self.make_pouring(
            fat_pct=Decimal("2.9"),
            adulteration=True,
        )

        result = process_pouring(pouring, member)

        self.assertEqual(result.status, "REJECTED")
        self.assertEqual(
            result.reject_reason, "ADULTERATION_POSITIVE"
        )
        self.assertEqual(
            member.suspended_until,
            pouring.pour_ts.date() + timedelta(days=7),
        )

    def test_member_is_rejected_on_seventh_suspension_day(self):
        member = self.make_member()
        member.suspended_until = datetime(2026, 11, 8).date()

        result = process_pouring(
            self.make_pouring(
                pour_ts=datetime(2026, 11, 8, 6, 0, 0)
            ),
            member,
        )

        self.assertEqual(result.status, "REJECTED")
        self.assertEqual(result.reject_reason, "MEMBER_SUSPENDED")

    def test_member_can_pour_after_suspension_expires(self):
        member = self.make_member()
        member.suspended_until = datetime(2026, 11, 8).date()

        result = process_pouring(
            self.make_pouring(
                pour_ts=datetime(2026, 11, 9, 6, 0, 0)
            ),
            member,
        )

        self.assertEqual(result.status, "ACCEPTED")

    def test_suspended_member_is_rejected(self):
        member = self.make_member()
        member.suspended_until = datetime(2026, 11, 7).date()

        result = process_pouring(
            self.make_pouring(
                pour_ts=datetime(2026, 11, 5, 6, 0, 0)
            ),
            member,
        )

        self.assertEqual(result.status, "REJECTED")
        self.assertEqual(result.reject_reason, "MEMBER_SUSPENDED")

    def test_inactive_member_is_rejected(self):
        member = self.make_member()
        member.status = "EXITED"

        result = process_pouring(self.make_pouring(), member)

        self.assertEqual(result.status, "REJECTED")
        self.assertEqual(result.reject_reason, "MEMBER_INACTIVE")

    def test_value_is_rounded_to_paisa(self):
        result = process_pouring(
            self.make_pouring(
                litres=Decimal("10.5"),
                fat_pct=Decimal("3.56"),
                snf_pct=Decimal("8.53"),
            ),
            self.make_member(),
        )

        self.assertEqual(result.chart_rate, Decimal("32.45"))
        self.assertEqual(result.value, Decimal("340.73"))


class ProcessPouringsTests(unittest.TestCase):

    def make_member(self):
        return Member("M001", "S001", "Ravi", "COW")

    def make_pouring(self, pouring_id="P001", **values):
        defaults = {
            "member_id": "M001",
            "pour_ts": datetime(2026, 11, 1, 6, 0, 0),
            "shift": "AM",
            "litres": Decimal("10.0"),
            "fat_pct": Decimal("3.5"),
            "snf_pct": Decimal("8.5"),
            "temp_c": Decimal("8"),
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

        self.assertEqual(results[0].status, "REJECTED")
        self.assertEqual(results[0].reject_reason, "INVALID_SHIFT")

    def test_invalid_litres_is_rejected(self):
        results = process_pourings(
            [self.make_pouring(litres=Decimal("10.15"))],
            {"M001": self.make_member()},
        )

        self.assertEqual(results[0].status, "REJECTED")
        self.assertEqual(results[0].reject_reason, "INVALID_LITRES")

    def test_unknown_member_is_rejected(self):
        results = process_pourings(
            [self.make_pouring(member_id="M999")],
            {"M001": self.make_member()},
        )

        self.assertEqual(results[0].status, "REJECTED")
        self.assertEqual(results[0].reject_reason, "UNKNOWN_MEMBER")

    def test_duplicate_pouring_id_is_rejected(self):
        pouring = self.make_pouring()

        results = process_pourings(
            [pouring, pouring],
            {"M001": self.make_member()},
        )

        self.assertEqual(results[0].status, "ACCEPTED")
        self.assertEqual(results[1].status, "REJECTED")
        self.assertEqual(
            results[1].reject_reason, "DUPLICATE_POURING"
        )


if __name__ == "__main__":
    unittest.main()
