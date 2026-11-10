
import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from models import Member
from member_exit_service import (
    calculate_exit_recoveries,
    calculate_member_exit_summary,
)


def make_member(
    feed_balance="0.00",
    loan_balance="0.00",
    loan_emi="0.00",
):
    return Member(
        member_id="M001",
        society_id="S001",
        member_name="Test Member",
        cattle_type="COW",
        prev_cycle_litres=Decimal("1000.0"),
        feed_advance_balance=Decimal(feed_balance),
        loan_balance=Decimal(loan_balance),
        loan_emi=Decimal(loan_emi),
    )


def make_result(day, value, member_id="M001"):
    pouring = SimpleNamespace(
        member_id=member_id,
        pour_ts=datetime(2026, 1, day, 6, 0),
        shift="AM",
        litres=Decimal("10.0"),
    )

    return SimpleNamespace(
        pouring=pouring,
        status="ACCEPTED",
        value=Decimal(value),
        sour_reversal=Decimal("0.00"),
    )


class MemberExitTests(unittest.TestCase):

    def test_exit_recovers_full_feed_and_loan_balances(self):
        recovery = calculate_exit_recoveries(
            gross=Decimal("1000.00"),
            feed_balance=Decimal("100.00"),
            loan_balance=Decimal("200.00"),
        )

        self.assertEqual(
            recovery["feed_recovery"], Decimal("100.00")
        )
        self.assertEqual(
            recovery["loan_recovery"], Decimal("200.00")
        )
        self.assertEqual(
            recovery["net_payment"], Decimal("700.00")
        )
        self.assertEqual(
            recovery["feed_balance_after"], Decimal("0.00")
        )
        self.assertEqual(
            recovery["loan_balance_after"], Decimal("0.00")
        )

    def test_exit_does_not_apply_500_payment_floor(self):
        recovery = calculate_exit_recoveries(
            gross=Decimal("400.00"),
            feed_balance=Decimal("100.00"),
            loan_balance=Decimal("200.00"),
        )

        self.assertEqual(
            recovery["feed_recovery"], Decimal("100.00")
        )
        self.assertEqual(
            recovery["loan_recovery"], Decimal("200.00")
        )
        self.assertEqual(
            recovery["net_payment"], Decimal("100.00")
        )

    def test_exit_calculates_only_until_exit_date(self):
        member = make_member()

        results = [
            make_result(2, "320.00"),
            make_result(7, "640.00"),
        ]

        summary = calculate_member_exit_summary(
            member, results, date(2026, 1, 5)
        )

        self.assertEqual(
            summary["pouring_value"], Decimal("320.00")
        )
        self.assertEqual(summary["gross"], Decimal("320.00"))
        self.assertEqual(
            summary["net_payment"], Decimal("320.00")
        )

    def test_exit_clears_balances_and_changes_member_status(self):
        member = make_member(
            feed_balance="100.00",
            loan_balance="200.00",
        )

        summary = calculate_member_exit_summary(
            member,
            [make_result(2, "1000.00")],
            date(2026, 1, 5),
        )

        self.assertEqual(member.status, "EXITED")
        self.assertEqual(
            member.feed_advance_balance, Decimal("0.00")
        )
        self.assertEqual(
            member.loan_balance, Decimal("0.00")
        )
        self.assertEqual(
            member.loan_carried, Decimal("0.00")
        )
        self.assertEqual(
            summary["feed_recovery"], Decimal("100.00")
        )
        self.assertEqual(
            summary["loan_recovery"], Decimal("200.00")
        )

    def test_exit_payment_date_is_exit_date(self):
        member = make_member()

        summary = calculate_member_exit_summary(
            member,
            [make_result(2, "1000.00")],
            date(2026, 1, 5),
        )

        self.assertEqual(
            summary["payment_date"], date(2026, 1, 5)
        )

    def test_inactive_member_cannot_exit_again(self):
        member = make_member()
        member.status = "EXITED"

        with self.assertRaisesRegex(
            ValueError, "MEMBER_NOT_ACTIVE"
        ):
            calculate_member_exit_summary(
                member,
                [],
                date(2026, 1, 5),
            )


if __name__ == "__main__":
    unittest.main()
