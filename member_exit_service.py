from datetime import date
from decimal import Decimal

from cycle_service import (
    calculate_member_cycle_summary,
    get_cycle_dates,
    money,
)


ZERO = Decimal("0.00")


def calculate_exit_recoveries(
    gross, feed_balance, loan_balance
):

    gross = money(gross)
    feed_recovery = money(feed_balance)
    loan_recovery = money(loan_balance)

    net_payment = money(
        gross - feed_recovery - loan_recovery
    )

    return {
        "feed_recovery": feed_recovery,
        "loan_recovery": loan_recovery,
        "loan_carried": ZERO,
        "feed_balance_after": ZERO,
        "loan_balance_after": ZERO,
        "net_payment": net_payment,
    }


def calculate_member_exit_summary(
    member, results, exit_date
):

    if not isinstance(exit_date, date):
        raise ValueError("INVALID_EXIT_DATE")

    if member.status != "ACTIVE":
        raise ValueError("MEMBER_NOT_ACTIVE")

    cycle_start, _ = get_cycle_dates(exit_date)

    outstanding_feed = money(member.feed_advance_balance)
    outstanding_loan = money(member.loan_balance)

    summary = calculate_member_cycle_summary(
        member,
        results,
        cycle_start,
        exit_date,
    )

    recovery = calculate_exit_recoveries(
        summary["gross"],
        outstanding_feed,
        outstanding_loan,
    )

    member.feed_advance_balance = ZERO
    member.loan_balance = ZERO
    member.loan_carried = ZERO
    member.status = "EXITED"

    summary.update(recovery)
    summary["payment_date"] = exit_date

    return summary
