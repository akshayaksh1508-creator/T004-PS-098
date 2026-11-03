import unittest
from decimal import Decimal

from app.money import multiply_money, to_money


class MoneyTests(unittest.TestCase):
    def test_to_money_rounds_to_paisa(self):
        self.assertEqual(to_money("32.456"), Decimal("32.46"))

    def test_multiply_money_rounds_the_total(self):
        self.assertEqual(
            multiply_money(Decimal("10.5"), Decimal("32.46")),
            Decimal("340.83"),
        )


if __name__ == "__main__":
    unittest.main()
