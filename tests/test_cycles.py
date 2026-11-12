import unittest
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from cycle_service import (
    get_cycle_dates,
    get_payment_date,
    count_shifts,
    calculate_accepted_litres,
    calculate_cycle_value,
    calculate_loyalty_bonus,
    calculate_lean_bonus,
    calculate_flush_threshold,
    calculate_flush_penalty,
    calculate_recoveries,
    calculate_member_cycle_summary,
)
from models import Member


def make_result(
    member_id="M-010",
    day=11,
    shift="AM",
    litres="10.0",
    status="ACCEPTED",
    month=1,
    value=None,
):
    pouring = SimpleNamespace(
        member_id=member_id,
        pour_ts=datetime(2026, month, day, 6, 0),
        shift=shift,
        litres=Decimal(litres),
    )

    if value is None:
        value = Decimal(litres) * Decimal("32.00")

    return SimpleNamespace(
        pouring=pouring,
        status=status,
        value=Decimal(str(value)),
        sour_reversal=Decimal("0.00"),
    )


def make_member(
    member_id="M-010",
    prev_cycle_litres="1000.0",
    feed_balance="0.00",
    loan_balance="0.00",
    loan_emi="0.00",
):
    return Member(
        member_id=member_id,
        society_id="S-1",
        member_name="Test Member",
        cattle_type="COW",
        prev_cycle_litres=Decimal(prev_cycle_litres),
        feed_advance_balance=Decimal(feed_balance),
        loan_balance=Decimal(loan_balance),
        loan_emi=Decimal(loan_emi),
    )


class CycleTests(unittest.TestCase):

    def test_first_cycle(self):
        self.assertEqual(
            get_cycle_dates(date(2026, 1, 5)),
            (date(2026, 1, 1), date(2026, 1, 10)),
        )

    def test_second_cycle(self):
        self.assertEqual(
            get_cycle_dates(date(2026, 1, 15)),
            (date(2026, 1, 11), date(2026, 1, 20)),
        )

    def test_third_cycle(self):
        self.assertEqual(
            get_cycle_dates(date(2026, 1, 25)),
            (date(2026, 1, 21), date(2026, 1, 31)),
        )

    def test_february_cycle(self):
        self.assertEqual(
            get_cycle_dates(date(2026, 2, 25)),
            (date(2026, 2, 21), date(2026, 2, 28)),
        )

    def test_leap_year_february_cycle(self):
        self.assertEqual(
            get_cycle_dates(date(2028, 2, 25)),
            (date(2028, 2, 21), date(2028, 2, 29)),
        )

    def test_december_cycle(self):
        self.assertEqual(
            get_cycle_dates(date(2026, 12, 25)),
            (date(2026, 12, 21), date(2026, 12, 31)),
        )

    def test_payment_date(self):
        self.assertEqual(
            get_payment_date(date(2026, 1, 20)),
            date(2026, 1, 23),
        )

    def test_payment_date_crosses_year(self):
        self.assertEqual(
            get_payment_date(date(2026, 12, 31)),
            date(2027, 1, 3),
        )

    def test_count_unique_shifts(self):
        results = [
            make_result(day=11, shift="AM"),
            make_result(day=11, shift="PM"),
            make_result(day=11, shift="AM"),
            make_result(day=12, shift="AM"),
        ]

        self.assertEqual(
            count_shifts(
                "M-010", results,
                date(2026, 1, 11), date(2026, 1, 20)
            ),
            3,
        )

    def test_rejected_pouring_not_counted(self):
        results = [
            make_result(day=11, status="ACCEPTED"),
            make_result(day=12, status="REJECTED"),
        ]

        self.assertEqual(
            count_shifts(
                "M-010", results,
                date(2026, 1, 11), date(2026, 1, 20)
            ),
            1,
        )

    def test_other_member_not_counted(self):
        results = [
            make_result(member_id="M-011"),
        ]

        self.assertEqual(
            count_shifts(
                "M-010", results,
                date(2026, 1, 11), date(2026, 1, 20)
            ),
            0,
        )

    def test_accepted_litres(self):
        results = [
            make_result(day=11, litres="10.0"),
            make_result(day=11, shift="PM", litres="8.5"),
            make_result(day=12, litres="5.0"),
            make_result(day=13, litres="4.0", status="REJECTED"),
        ]

        self.assertEqual(
            calculate_accepted_litres(
                "M-010", results,
                date(2026, 1, 11), date(2026, 1, 20)
            ),
            Decimal("23.5"),
        )

    def test_cycle_value_sums_values_and_sour_reversal(self):
        results = [
            make_result(day=11, value="100.00"),
            make_result(day=12, value="50.00"),
            make_result(day=13, value="99.00", status="REJECTED"),
        ]
        results[1].sour_reversal = Decimal("25.00")

        pouring_value, sour_reversal = calculate_cycle_value(
            "M-010", results,
            date(2026, 1, 11), date(2026, 1, 20)
        )

        self.assertEqual(pouring_value, Decimal("150.00"))
        self.assertEqual(sour_reversal, Decimal("25.00"))

    def test_loyalty_bonus_exactly_15_shifts(self):
        self.assertEqual(
            calculate_loyalty_bonus(15, Decimal("108.5")),
            Decimal("54.25"),
        )

    def test_no_loyalty_bonus_for_14_shifts(self):
        self.assertEqual(
            calculate_loyalty_bonus(14, Decimal("108.5")),
            Decimal("0.00"),
        )

    def test_member_cycle_summary(self):
        results = [
            make_result(day=11, litres="50.0"),
            make_result(day=12, litres="58.5"),
        ]

        summary = calculate_member_cycle_summary(
            make_member(),
            results,
            date(2026, 1, 11),
            date(2026, 1, 20),
        )

        self.assertEqual(summary["shifts_poured"], 2)
        self.assertEqual(
            summary["accepted_litres"], Decimal("108.5")
        )
        self.assertEqual(
            summary["loyalty_bonus"], Decimal("0.00")
        )
        self.assertEqual(
            summary["pouring_value"], Decimal("3472.00")
        )
        self.assertEqual(
            summary["flush_penalty"], Decimal("0.00")
        )
        self.assertEqual(summary["gross"], Decimal("3472.00"))
        self.assertEqual(summary["net_payment"], Decimal("3472.00"))
        self.assertEqual(
            summary["payment_date"], date(2026, 1, 23)
        )

    def test_ec04_exactly_15_shifts_earns_54_25(self):
        results = []

        for day in range(11, 21):
            results.append(
                make_result(
                    day=day,
                    shift="AM",
                    litres="7.0",
                )
            )

        for day in range(11, 15):
            results.append(
                make_result(
                    day=day,
                    shift="PM",
                    litres="7.0",
                )
            )

        results.append(
            make_result(
                day=15,
                shift="PM",
                litres="10.5",
            )
        )

        summary = calculate_member_cycle_summary(
            make_member(),
            results,
            date(2026, 1, 11),
            date(2026, 1, 20),
        )

        self.assertEqual(summary["shifts_poured"], 15)
        self.assertEqual(
            summary["accepted_litres"], Decimal("108.5")
        )
        self.assertEqual(
            summary["loyalty_bonus"], Decimal("54.25")
        )

    def test_ec05_february_15_shifts_qualifies_14_does_not(self):
        results = []

        for day in range(21, 29):
            results.append(
                make_result(
                    member_id="M-003",
                    day=day,
                    shift="AM",
                    litres="10.0",
                    month=2,
                )
            )

        for day in range(21, 28):
            results.append(
                make_result(
                    member_id="M-003",
                    day=day,
                    shift="PM",
                    litres="10.0",
                    month=2,
                )
            )

        for day in range(21, 28):
            results.append(
                make_result(
                    member_id="M-011",
                    day=day,
                    shift="AM",
                    litres="10.0",
                    month=2,
                )
            )

            results.append(
                make_result(
                    member_id="M-011",
                    day=day,
                    shift="PM",
                    litres="10.0",
                    month=2,
                )
            )

        start = date(2026, 2, 21)
        end = date(2026, 2, 28)

        summary_003 = calculate_member_cycle_summary(
            make_member(member_id="M-003"),
            results,
            start,
            end,
        )

        summary_011 = calculate_member_cycle_summary(
            make_member(member_id="M-011"),
            results,
            start,
            end,
        )

        self.assertEqual(summary_003["shifts_poured"], 15)
        self.assertEqual(
            summary_003["loyalty_bonus"], Decimal("75.00")
        )

        self.assertEqual(summary_011["shifts_poured"], 14)
        self.assertEqual(
            summary_011["loyalty_bonus"], Decimal("0.00")
        )


class SeasonalBonusTests(unittest.TestCase):

    def test_lean_bonus_applies_april_to_july(self):
        for month in (4, 5, 6, 7):
            cycle_start = date(2026, month, 1)
            self.assertEqual(
                calculate_lean_bonus(
                    cycle_start, Decimal("108.5")
                ),
                Decimal("108.50"),
            )

    def test_no_lean_bonus_outside_april_to_july(self):
        for month in (1, 2, 3, 8, 9, 10, 11, 12):
            cycle_start = date(2026, month, 1)
            self.assertEqual(
                calculate_lean_bonus(
                    cycle_start, Decimal("108.5")
                ),
                Decimal("0.00"),
            )

    def test_flush_threshold_uses_11_day_previous_cycle(self):
        self.assertEqual(
            calculate_flush_threshold(
                date(2026, 1, 1), Decimal("212.0")
            ),
            Decimal("28.9"),
        )

    def test_flush_threshold_uses_10_day_previous_cycle(self):
        self.assertEqual(
            calculate_flush_threshold(
                date(2026, 1, 11), Decimal("212.0")
            ),
            Decimal("31.8"),
        )

    def test_flush_penalty_only_on_litres_above_threshold(self):
        daily = {
            date(2026, 1, 1): Decimal("20.0"),
            date(2026, 1, 2): Decimal("10.0"),
            date(2026, 1, 3): Decimal("15.0"),
        }

        self.assertEqual(
            calculate_flush_penalty(daily, Decimal("15.0")),
            Decimal("1.25"),
        )

    def test_flush_penalty_rounds_half_up(self):
        daily = {date(2026, 1, 1): Decimal("12.5")}

        self.assertEqual(
            calculate_flush_penalty(daily, Decimal("10.0")),
            Decimal("0.63"),
        )

    def test_january_summary_applies_flush_penalty(self):
        member = make_member(
            member_id="M-009", prev_cycle_litres="36.2"
        )

        results = [
            make_result(day=1, litres="3.8", member_id="M-009"),
            make_result(day=7, litres="7.5", member_id="M-009"),
        ]

        summary = calculate_member_cycle_summary(
            member, results,
            date(2026, 1, 1), date(2026, 1, 10)
        )

        self.assertEqual(
            summary["flush_penalty"], Decimal("0.65")
        )
        self.assertEqual(
            summary["lean_bonus"], Decimal("0.00")
        )
        self.assertEqual(
            summary["pouring_value"], Decimal("361.60")
        )
        self.assertEqual(summary["gross"], Decimal("360.95"))
        self.assertEqual(
            summary["net_payment"], Decimal("360.95")
        )

    def test_april_summary_applies_lean_bonus(self):
        member = make_member()

        results = [
            make_result(day=5, litres="12.5", month=4),
        ]

        summary = calculate_member_cycle_summary(
            member, results,
            date(2026, 4, 1), date(2026, 4, 10)
        )

        self.assertEqual(
            summary["lean_bonus"], Decimal("12.50")
        )
        self.assertEqual(
            summary["flush_penalty"], Decimal("0.00")
        )
        self.assertEqual(summary["gross"], Decimal("412.50"))


class RecoveryTests(unittest.TestCase):

    def test_ec06_feed_cleared_and_exact_two_times_emi(self):
        recovery = calculate_recoveries(
            gross=Decimal("7636.88"),
            feed_balance=Decimal("836.88"),
            loan_balance=Decimal("40800.00"),
            loan_emi=Decimal("3400.00"),
        )

        self.assertEqual(
            recovery["feed_recovery"], Decimal("836.88")
        )
        self.assertEqual(
            recovery["loan_recovery"], Decimal("3400.00")
        )
        self.assertEqual(
            recovery["loan_carried"], Decimal("0.00")
        )
        self.assertEqual(
            recovery["net_payment"], Decimal("3400.00")
        )
        self.assertEqual(
            recovery["feed_balance_after"], Decimal("0.00")
        )
        self.assertEqual(
            recovery["loan_balance_after"], Decimal("37400.00")
        )

    def test_half_emi_when_below_two_times(self):
        recovery = calculate_recoveries(
            gross=Decimal("2000.00"),
            feed_balance=Decimal("0.00"),
            loan_balance=Decimal("5000.00"),
            loan_emi=Decimal("1200.00"),
        )

        self.assertEqual(
            recovery["loan_recovery"], Decimal("600.00")
        )
        self.assertEqual(
            recovery["loan_carried"], Decimal("600.00")
        )
        self.assertEqual(
            recovery["net_payment"], Decimal("1400.00")
        )

    def test_m009_floor_cuts_loan_recovery_to_keep_net_500(self):
        recovery = calculate_recoveries(
            gross=Decimal("1264.16"),
            feed_balance=Decimal("4000.00"),
            loan_balance=Decimal("20000.00"),
            loan_emi=Decimal("1600.00"),
        )

        self.assertEqual(
            recovery["feed_recovery"], Decimal("252.83")
        )
        self.assertEqual(
            recovery["loan_recovery"], Decimal("511.33")
        )
        self.assertEqual(
            recovery["loan_carried"], Decimal("1088.67")
        )
        self.assertEqual(
            recovery["net_payment"], Decimal("500.00")
        )
        self.assertEqual(
            recovery["loan_balance_after"], Decimal("19488.67")
        )

    def test_no_recovery_when_gross_below_500(self):
        recovery = calculate_recoveries(
            gross=Decimal("400.00"),
            feed_balance=Decimal("100.00"),
            loan_balance=Decimal("200.00"),
            loan_emi=Decimal("50.00"),
        )

        self.assertEqual(
            recovery["feed_recovery"], Decimal("0.00")
        )
        self.assertEqual(
            recovery["loan_recovery"], Decimal("0.00")
        )
        self.assertEqual(
            recovery["loan_carried"], Decimal("50.00")
        )
        self.assertEqual(
            recovery["net_payment"], Decimal("400.00")
        )

    def test_feed_recovery_capped_by_feed_balance(self):
        recovery = calculate_recoveries(
            gross=Decimal("1000.00"),
            feed_balance=Decimal("100.00"),
            loan_balance=Decimal("0.00"),
            loan_emi=Decimal("0.00"),
        )

        self.assertEqual(
            recovery["feed_recovery"], Decimal("100.00")
        )
        self.assertEqual(
            recovery["feed_balance_after"], Decimal("0.00")
        )

    def test_loan_due_capped_by_loan_balance(self):
        recovery = calculate_recoveries(
            gross=Decimal("5000.00"),
            feed_balance=Decimal("0.00"),
            loan_balance=Decimal("300.00"),
            loan_emi=Decimal("500.00"),
        )

        self.assertEqual(
            recovery["loan_recovery"], Decimal("300.00")
        )
        self.assertEqual(
            recovery["loan_carried"], Decimal("0.00")
        )

    def test_floor_cuts_loan_first_then_feed(self):
        recovery = calculate_recoveries(
            gross=Decimal("1000.00"),
            feed_balance=Decimal("1000.00"),
            loan_balance=Decimal("5000.00"),
            loan_emi=Decimal("1000.00"),
        )

        self.assertEqual(
            recovery["feed_recovery"], Decimal("200.00")
        )
        self.assertEqual(
            recovery["loan_recovery"], Decimal("300.00")
        )
        self.assertEqual(
            recovery["loan_carried"], Decimal("700.00")
        )
        self.assertEqual(
            recovery["net_payment"], Decimal("500.00")
        )

    def test_carried_emi_is_added_to_next_cycle_due(self):
        recovery = calculate_recoveries(
            gross=Decimal("2000.00"),
            feed_balance=Decimal("0.00"),
            loan_balance=Decimal("5000.00"),
            loan_emi=Decimal("1000.00"),
            loan_carried=Decimal("300.00"),
        )

        self.assertEqual(
            recovery["loan_recovery"], Decimal("650.00")
        )
        self.assertEqual(
            recovery["loan_carried"], Decimal("650.00")
        )
        self.assertEqual(
            recovery["net_payment"], Decimal("1350.00")
        )

    def test_ec06_summary_clears_feed_and_full_emi(self):
        member = make_member(
            member_id="M-001",
            prev_cycle_litres="212.0",
            feed_balance="836.88",
            loan_balance="40800.00",
            loan_emi="3400.00",
        )

        results = [
            make_result(
                day=1, litres="10.0", value="3818.44",
                member_id="M-001",
            ),
            make_result(
                day=2, litres="10.0", value="3818.44",
                member_id="M-001",
            ),
        ]

        summary = calculate_member_cycle_summary(
            member, results,
            date(2026, 1, 1), date(2026, 1, 10)
        )

        self.assertEqual(summary["gross"], Decimal("7636.88"))
        self.assertEqual(
            summary["feed_recovery"], Decimal("836.88")
        )
        self.assertEqual(
            summary["loan_recovery"], Decimal("3400.00")
        )
        self.assertEqual(
            summary["loan_carried"], Decimal("0.00")
        )
        self.assertEqual(
            summary["net_payment"], Decimal("3400.00")
        )
        self.assertEqual(
            summary["feed_balance_after"], Decimal("0.00")
        )
        self.assertEqual(
            summary["loan_balance_after"], Decimal("37400.00")
        )
        self.assertEqual(
            member.feed_advance_balance, Decimal("0.00")
        )
        self.assertEqual(
            member.loan_balance, Decimal("37400.00")
        )
        self.assertEqual(
            member.prev_cycle_litres, Decimal("20.0")
        )

    def test_m009_summary_floor_keeps_net_500(self):
        member = make_member(
            member_id="M-009",
            prev_cycle_litres="36.2",
            feed_balance="4000.00",
            loan_balance="20000.00",
            loan_emi="1600.00",
        )

        results = [
            make_result(
                day=1, litres="3.8", value="632.40",
                member_id="M-009",
            ),
            make_result(
                day=2, litres="2.9", value="632.40",
                member_id="M-009",
            ),
            make_result(
                day=7, litres="7.5", value="0.01",
                member_id="M-009",
            ),
        ]

        summary = calculate_member_cycle_summary(
            member, results,
            date(2026, 1, 1), date(2026, 1, 10)
        )

        self.assertEqual(
            summary["flush_penalty"], Decimal("0.65")
        )
        self.assertEqual(summary["gross"], Decimal("1264.16"))
        self.assertEqual(
            summary["feed_recovery"], Decimal("252.83")
        )
        self.assertEqual(
            summary["loan_recovery"], Decimal("511.33")
        )
        self.assertEqual(
            summary["loan_carried"], Decimal("1088.67")
        )
        self.assertEqual(
            summary["net_payment"], Decimal("500.00")
        )
        self.assertEqual(
            member.loan_balance, Decimal("19488.67")
        )
        self.assertEqual(
            member.loan_carried, Decimal("1088.67")
        )


if __name__ == "__main__":
    unittest.main()
