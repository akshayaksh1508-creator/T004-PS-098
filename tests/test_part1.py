import unittest
from decimal import Decimal

from models import Member, Society
from validators import is_valid_cattle_type, is_valid_litres, is_valid_shift


class PartOneTests(unittest.TestCase):
    def test_member_can_be_created(self):
        member = Member("M001", "S001", "Ravi", "COW")
        self.assertEqual(member.member_id, "M001")
        self.assertEqual(member.status, "ACTIVE")

    def test_society_can_be_created(self):
        society = Society("S001", "U001", "Village Society", Decimal("2.5"), Decimal("20"))
        self.assertEqual(society.commission_rate, Decimal("2.5"))

    def test_valid_shift(self):
        self.assertTrue(is_valid_shift("AM"))
        self.assertTrue(is_valid_shift("PM"))
        self.assertFalse(is_valid_shift("NIGHT"))

    def test_valid_litres(self):
        self.assertTrue(is_valid_litres("10.1"))
        self.assertFalse(is_valid_litres("10.15"))

    def test_valid_cattle_type(self):
        self.assertTrue(is_valid_cattle_type("COW"))
        self.assertFalse(is_valid_cattle_type("GOAT"))


if __name__ == "__main__":
    unittest.main()
