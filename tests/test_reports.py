
import csv
import os
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal

from models import Member, Pouring
from pouring_service import process_pourings
from reports import (
    REGISTER_COLUMNS,
    DISPUTE_RESULT_COLUMNS,
    write_collection_register,
    write_dispute_results,
)


class ReportTests(unittest.TestCase):

    def make_results(self):
        member = Member("M001", "S001", "Ravi", "COW")

        pourings = [
            Pouring(
                "P001", "M001", datetime(2026, 11, 1, 6, 0, 0), "AM",
                Decimal("10.0"), Decimal("3.5"), Decimal("8.5"),
                Decimal("8"), False, "CAN1",
            ),
            Pouring(
                "P002", "M001", datetime(2026, 11, 1, 18, 0, 0), "PM",
                Decimal("5.0"), Decimal("3.5"), Decimal("8.5"),
                Decimal("8"), False, "CAN2",
            ),
            Pouring(
                "P003", "M001", datetime(2026, 11, 2, 6, 0, 0), "AM",
                Decimal("4.0"), Decimal("2.9"), Decimal("8.5"),
                Decimal("8"), False, "CAN3",
            ),
        ]

        return process_pourings(pourings, {"M001": member})

    def test_register_has_exact_columns(self):
        with tempfile.TemporaryDirectory() as folder:
            file_name = os.path.join(folder, "register.csv")

            write_collection_register(self.make_results(), file_name)

            with open(file_name, "r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(list(rows[0].keys()), REGISTER_COLUMNS)

    def test_register_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            file_name = os.path.join(folder, "register.csv")

            write_collection_register(self.make_results(), file_name)

            with open(file_name, "r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(len(rows), 3)

            self.assertEqual(rows[0]["pouring_id"], "P001")
            self.assertEqual(rows[0]["pour_ts"], "2026-11-01 06:00:00")
            self.assertEqual(rows[0]["chart_id"], "COW")
            self.assertEqual(rows[0]["chart_rate"], "32.00")
            self.assertEqual(rows[0]["price_per_litre"], "32.00")
            self.assertEqual(rows[0]["value"], "320.00")
            self.assertEqual(rows[0]["status"], "ACCEPTED")
            self.assertEqual(rows[0]["reject_reason"], "")
            self.assertEqual(rows[0]["sour_reversal"], "0.00")

            self.assertEqual(rows[1]["value"], "160.00")

            self.assertEqual(rows[2]["status"], "REJECTED")
            self.assertEqual(rows[2]["reject_reason"], "FAT_TOO_LOW")
            self.assertEqual(rows[2]["chart_id"], "")
            self.assertEqual(rows[2]["chart_rate"], "0.00")

    # New dispute report tests

    def test_dispute_report_has_exact_columns(self):
        results = [
            {
                "test_id": "RT-001",
                "pouring_id": "P001",
                "status": "ACCEPTED",
                "parameter": "FAT",
                "original_value": "3.90",
                "retest_value": "4.05",
                "value_used": "4.05",
            }
        ]

        with tempfile.TemporaryDirectory() as folder:
            file_name = os.path.join(folder, "disputes.csv")

            write_dispute_results(results, file_name)

            with open(file_name, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                rows = list(reader)

            self.assertEqual(
                reader.fieldnames,
                DISPUTE_RESULT_COLUMNS,
            )
            self.assertEqual(len(rows), 1)

    def test_dispute_report_writes_multiple_results(self):
        results = [
            {
                "test_id": "RT-001",
                "pouring_id": "P001",
                "status": "ACCEPTED",
                "parameter": "FAT",
                "original_value": "3.90",
                "retest_value": "4.05",
                "value_used": "4.05",
            },
            {
                "test_id": "RT-002",
                "pouring_id": "P002",
                "status": "REJECTED",
                "parameter": "SNF",
                "original_value": "8.50",
                "retest_value": "8.40",
                "value_used": "8.50",
            },
        ]

        with tempfile.TemporaryDirectory() as folder:
            file_name = os.path.join(folder, "disputes.csv")

            write_dispute_results(results, file_name)

            with open(file_name, "r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["test_id"], "RT-001")
            self.assertEqual(rows[0]["value_used"], "4.05")
            self.assertEqual(rows[1]["test_id"], "RT-002")
            self.assertEqual(rows[1]["status"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
