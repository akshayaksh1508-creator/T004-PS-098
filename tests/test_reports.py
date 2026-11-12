import csv
import os
import tempfile
import unittest
from datetime import date, datetime
from decimal import Decimal

from models import Member, Pouring
from pouring_service import process_pourings
from reports import (
    REGISTER_COLUMNS,
    DISPUTE_RESULT_COLUMNS,
    MEMBER_STATEMENT_COLUMNS,
    SOCIETY_SETTLEMENT_COLUMNS,
    write_collection_register,
    write_dispute_results,
    write_member_statements,
    write_society_settlements,
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


    def test_dispute_result_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            file_name = os.path.join(folder, "disputes.csv")

            write_dispute_results(
                [
                    {
                        "test_id": "RT-001",
                        "pouring_id": "PR-00036",
                        "status": "ACCEPTED",
                        "parameter": "FAT",
                        "original_value": "4.34",
                        "retest_value": "4.49",
                        "value_used": "4.49",
                    }
                ],
                file_name,
            )

            with open(file_name, "r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(
                list(rows[0].keys()), DISPUTE_RESULT_COLUMNS
            )
            self.assertEqual(rows[0]["test_id"], "RT-001")
            self.assertEqual(rows[0]["value_used"], "4.49")


class MemberStatementWriterTests(unittest.TestCase):

    def make_summary(self):
        return {
            "cycle_start": date(2026, 1, 11),
            "cycle_end": date(2026, 1, 20),
            "member_id": "M-010",
            "shifts_poured": 15,
            "accepted_litres": Decimal("108.5"),
            "pouring_value": Decimal("3472.00"),
            "sour_reversal": Decimal("0.00"),
            "loyalty_bonus": Decimal("54.25"),
            "lean_bonus": Decimal("0.00"),
            "flush_penalty": Decimal("0.00"),
            "gross": Decimal("3526.25"),
            "feed_recovery": Decimal("0.00"),
            "loan_recovery": Decimal("0.00"),
            "loan_carried": Decimal("0.00"),
            "net_payment": Decimal("3526.25"),
            "payment_date": date(2026, 1, 23),
            "feed_balance_after": Decimal("0.00"),
            "loan_balance_after": Decimal("0.00"),
        }

    def test_member_statement_columns_and_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            file_name = os.path.join(folder, "statements.csv")

            write_member_statements(
                [self.make_summary()], file_name
            )

            with open(file_name, "r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(
                list(rows[0].keys()), MEMBER_STATEMENT_COLUMNS
            )
            self.assertEqual(rows[0]["member_id"], "M-010")
            self.assertEqual(rows[0]["cycle_start"], "2026-01-11")
            self.assertEqual(rows[0]["payment_date"], "2026-01-23")
            self.assertEqual(rows[0]["shifts_poured"], "15")
            self.assertEqual(
                rows[0]["pouring_value"], "3472.00"
            )
            self.assertEqual(
                rows[0]["net_payment"], "3526.25"
            )

    def test_member_statements_sorted_by_member(self):
        with tempfile.TemporaryDirectory() as folder:
            file_name = os.path.join(folder, "statements.csv")

            summary_m003 = self.make_summary()
            summary_m003["member_id"] = "M-003"

            summary_m011 = self.make_summary()
            summary_m011["member_id"] = "M-011"

            write_member_statements(
                [summary_m011, summary_m003], file_name
            )

            with open(file_name, "r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(
                [row["member_id"] for row in rows],
                ["M-003", "M-011"],
            )


class SocietySettlementWriterTests(unittest.TestCase):

    def make_settlement(self, forfeited=False):
        return {
            "cycle_start": date(2026, 1, 11),
            "cycle_end": date(2026, 1, 20),
            "society_id": "S-2",
            "accepted_litres": Decimal("250.0"),
            "pouring_value": Decimal("8000.00"),
            "commission": (
                Decimal("0.00") if forfeited else Decimal("200.00")
            ),
            "handling": (
                Decimal("0.00") if forfeited else Decimal("50.00")
            ),
            "commission_forfeited": forfeited,
            "transport_subsidy": Decimal("37.50"),
            "sour_milk_share": Decimal("120.00"),
            "net_settlement": (
                Decimal("0.00") + Decimal("0.00")
                + Decimal("37.50") - Decimal("120.00")
                if forfeited
                else Decimal("200.00") + Decimal("50.00")
                + Decimal("37.50") - Decimal("120.00")
            ),
        }

    def test_society_settlement_columns_and_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            file_name = os.path.join(folder, "settlements.csv")

            write_society_settlements(
                [self.make_settlement()], file_name
            )

            with open(file_name, "r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(
                list(rows[0].keys()),
                SOCIETY_SETTLEMENT_COLUMNS,
            )
            self.assertEqual(rows[0]["society_id"], "S-2")
            self.assertEqual(
                rows[0]["commission"], "200.00"
            )
            self.assertEqual(
                rows[0]["commission_forfeited"], "false"
            )
            self.assertEqual(
                rows[0]["net_settlement"], "167.50"
            )

    def test_forfeited_flag_is_written_as_true(self):
        with tempfile.TemporaryDirectory() as folder:
            file_name = os.path.join(folder, "settlements.csv")

            write_society_settlements(
                [self.make_settlement(forfeited=True)], file_name
            )

            with open(file_name, "r", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(
                rows[0]["commission_forfeited"], "true"
            )
            self.assertEqual(rows[0]["commission"], "0.00")
            self.assertEqual(rows[0]["handling"], "0.00")
            self.assertEqual(
                rows[0]["transport_subsidy"], "37.50"
            )


if __name__ == "__main__":
    unittest.main()
