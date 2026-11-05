import csv
import os
import tempfile
import unittest
from datetime import date
from decimal import Decimal

from models import Member, Pouring
from pouring_service import process_pourings
from reports import (
    generate_daily_collection_register,
    write_daily_collection_register,
    write_pouring_prices,
)


class ReportTests(unittest.TestCase):

    def make_results(self):
        member = Member("M001", "S001", "Ravi", "COW")

        pourings = [
            Pouring(
                "P001", "M001", "S001", date(2026, 11, 1), "AM",
                Decimal("10.0"), Decimal("3.5"), Decimal("8.5"),
                Decimal("8"), False, "CAN1",
            ),
            Pouring(
                "P002", "M001", "S001", date(2026, 11, 1), "PM",
                Decimal("5.0"), Decimal("3.5"), Decimal("8.5"),
                Decimal("8"), False, "CAN2",
            ),
            Pouring(
                "P003", "M001", "S001", date(2026, 11, 2), "AM",
                Decimal("4.0"), Decimal("2.9"), Decimal("8.5"),
                Decimal("8"), False, "CAN3",
            ),
        ]

        return process_pourings(pourings, {"M001": member})

    def test_daily_register_totals(self):
        register = generate_daily_collection_register(self.make_results())

        self.assertEqual(len(register), 2)

        key = (date(2026, 11, 1), "S001", "COW")
        self.assertEqual(register[key]["total_pourings"], 2)
        self.assertEqual(register[key]["accepted_pourings"], 2)
        self.assertEqual(register[key]["received_litres"], Decimal("15.0"))
        self.assertEqual(register[key]["gross_value"], Decimal("480.00"))

        key = (date(2026, 11, 2), "S001", "UNKNOWN")
        self.assertEqual(register[key]["rejected_pourings"], 1)
        self.assertEqual(register[key]["rejected_litres"], Decimal("4.0"))

    def test_write_daily_collection_register(self):
        with tempfile.TemporaryDirectory() as folder:
            file_name = os.path.join(folder, "register.csv")

            write_daily_collection_register(
                self.make_results(), file_name
            )

            with open(file_name, "r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["date"], "2026-11-01")
            self.assertEqual(rows[0]["milk_type"], "COW")
            self.assertEqual(rows[0]["accepted_litres"], "15.0")

    def test_write_pouring_prices(self):
        with tempfile.TemporaryDirectory() as folder:
            file_name = os.path.join(folder, "prices.csv")

            write_pouring_prices(self.make_results(), file_name)

            with open(file_name, "r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["price_per_litre"], "32.00")
            self.assertEqual(rows[0]["value"], "320.00")
            self.assertEqual(rows[2]["rejection_reason"], "FAT_TOO_LOW")


if __name__ == "__main__":
    unittest.main()
