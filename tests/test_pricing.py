import unittest
from decimal import Decimal

from pricing import (
    determine_milk_type,
    get_rate_chart,
    calculate_base_price
)


class TestPricing(unittest.TestCase):

    def test_cow_milk(self):
        self.assertEqual(
            determine_milk_type("4.0", "COW"), "COW"
        )

    def test_buffalo_milk(self):
        self.assertEqual(
            determine_milk_type("5.5", "COW"), "BUFFALO"
        )

    def test_mixed_milk(self):
        self.assertEqual(
            determine_milk_type("5.5", "MIXED"), "COW"
        )

    def test_low_fat_rejected(self):
        with self.assertRaises(ValueError):
            determine_milk_type("2.9", "COW")

    def test_cow_base_price(self):
        chart = get_rate_chart("COW")
        self.assertEqual(
            calculate_base_price(chart, "3.5", "8.5"),
            Decimal("32.00")
        )

    def test_buffalo_base_price(self):
        chart = get_rate_chart("BUFFALO")
        self.assertEqual(
            calculate_base_price(chart, "6.0", "9.0"),
            Decimal("48.00")
        )

    def test_interpolation(self):
        chart = get_rate_chart("COW")

        result = calculate_base_price(
            chart, "3.55", "8.55"
        )

        self.assertEqual(result, Decimal("32.45"))

    def test_exactly_five_fat_uses_cow_chart(self):
        self.assertEqual(
            determine_milk_type("5.0", "COW"), "COW"
        )

    def test_above_five_fat_uses_buffalo_chart(self):
        self.assertEqual(
            determine_milk_type("5.1", "COW"), "BUFFALO"
        )

if __name__ == "__main__":
    unittest.main()