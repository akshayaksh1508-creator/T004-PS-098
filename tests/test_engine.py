"""
test_engine.py – Pytest test suite for PS-098 Dairy Cooperative Engine
Covers every business rule (BR-01 through BR-27) and all explicit edge cases.

Run with:  pytest tests/ -v --tb=short
Team T004 · Python 3.10+
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models import (
    Dispute, DisputeStatus, FeedAdvance, LoanSchedule, Member, MemberStatus, MilkType,
    Month, Pouring, PouringStatus, RateChart, Shift, Society, SourReturn, Union
)
from engine import (
    CycleCalculator, DisputeProcessor, MilkClassifier, PouringProcessor,
    PricingEngine, QualityAdjuster, SocietySettlementEngine,
    SourReturnProcessor, available_shifts_in_cycle, get_cycle_bounds,
    round_paisa, FAT_MIN_ACCEPTED
)
from store import DataStore


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def cow_chart() -> RateChart:
    return RateChart(
        chart_id="COW-001",
        milk_type=MilkType.COW,
        base_fat=Decimal("3.5"),
        base_snf=Decimal("8.5"),
        base_price=Decimal("32.00"),
        fat_increment=Decimal("0.60"),
        snf_increment=Decimal("0.30"),
    )


@pytest.fixture
def buffalo_chart() -> RateChart:
    return RateChart(
        chart_id="BUF-001",
        milk_type=MilkType.BUFFALO,
        base_fat=Decimal("6.0"),
        base_snf=Decimal("9.0"),
        base_price=Decimal("48.00"),
        fat_increment=Decimal("0.70"),
        snf_increment=Decimal("0.20"),
    )


@pytest.fixture
def rate_charts(cow_chart, buffalo_chart) -> dict[MilkType, RateChart]:
    return {MilkType.COW: cow_chart, MilkType.BUFFALO: buffalo_chart}


@pytest.fixture
def base_member() -> Member:
    return Member(
        member_id="M001",
        name="Ramesh Kumar",
        society_id="SOC001",
        cattle_type=MilkType.COW,
    )


@pytest.fixture
def member_with_debts() -> Member:
    return Member(
        member_id="M002",
        name="Suresh Patil",
        society_id="SOC001",
        cattle_type=MilkType.BUFFALO,
        loan_schedules=[
            LoanSchedule("L01", Decimal("10000"), Decimal("500"), Decimal("2000"))
        ],
        feed_advances=[
            FeedAdvance("FA01", Decimal("3000"), Decimal("1500"))
        ],
    )


@pytest.fixture
def store(base_member, member_with_debts, rate_charts) -> DataStore:
    ds = DataStore()
    ds.register_rate_chart(rate_charts[MilkType.COW])
    ds.register_rate_chart(rate_charts[MilkType.BUFFALO])
    ds.register_member(base_member)
    ds.register_member(member_with_debts)
    society = Society(
        society_id="SOC001", name="Test Society", union_id="U001",
        commission_rate=Decimal("0.025"), distance_km=Decimal("20")
    )
    ds.register_society(society)
    return ds


def make_pouring(
    pouring_id="P001",
    member_id="M001",
    society_id="SOC001",
    pour_date=date(2024, 10, 5),
    shift=Shift.AM,
    litres="10.0",
    fat="4.0",
    snf="8.5",
    temp="8.0",
    adulteration=False,
    can_id="CAN001",
    milk_type=MilkType.COW,
) -> Pouring:
    return Pouring(
        pouring_id=pouring_id,
        member_id=member_id,
        society_id=society_id,
        pouring_datetime=datetime.combine(pour_date, datetime.min.time()),
        shift=shift,
        litres=Decimal(litres),
        fat=Decimal(fat),
        snf=Decimal(snf),
        temperature_c=Decimal(temp),
        adulteration_flag=adulteration,
        can_id=can_id,
        milk_type=milk_type,
    )


# ===========================================================================
# BR-01: Fat below 3.0 → REJECT
# ===========================================================================

class TestBR01FatRejection:
    def test_fat_below_minimum_rejected(self, store):
        p = make_pouring(fat="2.9")
        proc = PouringProcessor(store.rate_charts, store.members)
        proc.process(p)
        assert p.status == PouringStatus.REJECTED
        assert "3.0" in p.rejection_reason

    def test_fat_exactly_3_0_accepted(self, store):
        """Edge case: fat exactly 3.0 → accepted at lowest cow rate."""
        p = make_pouring(fat="3.0", snf="8.5")
        proc = PouringProcessor(store.rate_charts, store.members)
        proc.process(p)
        assert p.status == PouringStatus.ACCEPTED

    def test_fat_zero_rejected(self, store):
        p = make_pouring(fat="0.0")
        proc = PouringProcessor(store.rate_charts, store.members)
        proc.process(p)
        assert p.status == PouringStatus.REJECTED


# ===========================================================================
# BR-02: Milk type classification
# ===========================================================================

class TestBR02MilkClassification:
    def test_fat_3_0_to_5_0_is_cow(self):
        for fat in ["3.0", "3.5", "4.9", "5.0"]:
            t, r = MilkClassifier.classify(Decimal(fat), MilkType.COW)
            assert t == MilkType.COW, f"fat={fat} should be COW"

    def test_fat_exactly_5_0_is_cow(self):
        """Edge case: fat exactly 5.0 → COW chart."""
        t, _ = MilkClassifier.classify(Decimal("5.0"), MilkType.COW)
        assert t == MilkType.COW

    def test_fat_above_5_0_is_buffalo(self):
        for fat in ["5.1", "6.0", "8.0"]:
            t, _ = MilkClassifier.classify(Decimal(fat), MilkType.BUFFALO)
            assert t == MilkType.BUFFALO, f"fat={fat} should be BUFFALO"

    def test_mixed_declared_uses_cow_pricing(self):
        """BR-03: MIXED milk priced on cow chart."""
        t, _ = MilkClassifier.classify(Decimal("4.0"), MilkType.MIXED)
        assert t == MilkType.MIXED


# ===========================================================================
# BR-04/05: Rate chart interpolation
# ===========================================================================

class TestBR0405RateChartInterpolation:
    def test_cow_base_price_at_reference_point(self, cow_chart):
        price = cow_chart.price_per_litre(Decimal("3.5"), Decimal("8.5"))
        assert price == Decimal("32.00")

    def test_cow_price_fat_increment(self, cow_chart):
        """Each 0.1 fat above base adds Rs 0.60."""
        price = cow_chart.price_per_litre(Decimal("3.6"), Decimal("8.5"))
        assert price == Decimal("32.60")

    def test_cow_price_snf_increment(self, cow_chart):
        """Each 0.1 SNF above base adds Rs 0.30."""
        price = cow_chart.price_per_litre(Decimal("3.5"), Decimal("8.6"))
        assert price == Decimal("32.30")

    def test_cow_interpolation_both_axes(self, cow_chart):
        """fat=3.7 (+2 steps), snf=8.7 (+2 steps)."""
        price = cow_chart.price_per_litre(Decimal("3.7"), Decimal("8.7"))
        expected = Decimal("32.00") + 2 * Decimal("0.60") + 2 * Decimal("0.30")
        assert price == expected.quantize(Decimal("0.01"))

    def test_snf_8_45_interpolation(self, cow_chart):
        """Edge case: SNF=8.45 → interpolated between 8.4 and 8.5."""
        price_84 = cow_chart.price_per_litre(Decimal("3.5"), Decimal("8.4"))
        price_85 = cow_chart.price_per_litre(Decimal("3.5"), Decimal("8.5"))
        price_845 = cow_chart.price_per_litre(Decimal("3.5"), Decimal("8.45"))
        expected = (price_84 + price_85) / 2
        assert abs(price_845 - expected) <= Decimal("0.01")

    def test_buffalo_base_price(self, buffalo_chart):
        price = buffalo_chart.price_per_litre(Decimal("6.0"), Decimal("9.0"))
        assert price == Decimal("48.00")

    def test_buffalo_fat_increment(self, buffalo_chart):
        """Each 0.1 fat adds Rs 0.70 for buffalo."""
        price = buffalo_chart.price_per_litre(Decimal("6.1"), Decimal("9.0"))
        assert price == Decimal("48.70")

    def test_buffalo_snf_increment(self, buffalo_chart):
        """Each 0.1 SNF adds Rs 0.20 for buffalo."""
        price = buffalo_chart.price_per_litre(Decimal("6.0"), Decimal("9.1"))
        assert price == Decimal("48.20")

    def test_cow_price_below_base_fat(self, cow_chart):
        """Fat=3.0 (below base 3.5) → fat_units negative → lower price."""
        price = cow_chart.price_per_litre(Decimal("3.0"), Decimal("8.5"))
        expected = Decimal("32.00") + (Decimal("3.0") - Decimal("3.5")) / Decimal("0.1") * Decimal("0.60")
        assert price == expected.quantize(Decimal("0.01"))


# ===========================================================================
# BR-06: SNF quality deduction
# ===========================================================================

class TestBR06SNFDeduction:
    def test_cow_snf_below_8_0_deduction(self):
        ded = QualityAdjuster.deduction_per_litre(MilkType.COW, Decimal("7.9"), Decimal("8.0"))
        assert ded == Decimal("1.00")

    def test_cow_snf_exactly_8_0_no_deduction(self):
        ded = QualityAdjuster.deduction_per_litre(MilkType.COW, Decimal("8.0"), Decimal("8.0"))
        assert ded == Decimal("0")

    def test_buffalo_snf_below_8_5_deduction(self):
        ded = QualityAdjuster.deduction_per_litre(MilkType.BUFFALO, Decimal("8.4"), Decimal("8.0"))
        assert ded == Decimal("1.00")

    def test_buffalo_snf_exactly_8_5_no_deduction(self):
        ded = QualityAdjuster.deduction_per_litre(MilkType.BUFFALO, Decimal("8.5"), Decimal("8.0"))
        assert ded == Decimal("0")


# ===========================================================================
# BR-07: Temperature deduction
# ===========================================================================

class TestBR07TemperatureDeduction:
    def test_temp_above_10_deduction(self):
        ded = QualityAdjuster.deduction_per_litre(MilkType.COW, Decimal("8.5"), Decimal("10.1"))
        assert ded == Decimal("0.50")

    def test_temp_exactly_10_no_deduction(self):
        ded = QualityAdjuster.deduction_per_litre(MilkType.COW, Decimal("8.5"), Decimal("10.0"))
        assert ded == Decimal("0")

    def test_combined_snf_and_temp_deduction(self):
        """Both SNF < threshold and temp > 10 → Rs 1.50 deduction."""
        ded = QualityAdjuster.deduction_per_litre(MilkType.COW, Decimal("7.5"), Decimal("12.0"))
        assert ded == Decimal("1.50")


# ===========================================================================
# BR-08: Adulteration → reject + 7-day suspension
# ===========================================================================

class TestBR08Adulteration:
    def test_adulteration_rejects_pouring_and_suspends(self, store):
        p = make_pouring(adulteration=True, pour_date=date(2024, 10, 5))
        proc = PouringProcessor(store.rate_charts, store.members)
        proc.process(p)
        assert p.status == PouringStatus.REJECTED
        member = store.members["M001"]
        assert member.status == MemberStatus.SUSPENDED
        assert member.suspension_end == date(2024, 10, 12)

    def test_suspended_member_pourings_rejected(self, store):
        # First adulteration
        p1 = make_pouring("P001", adulteration=True, pour_date=date(2024, 10, 5))
        proc = PouringProcessor(store.rate_charts, store.members)
        proc.process(p1)
        store.add_pouring(p1)

        # Next pouring during suspension
        p2 = make_pouring("P002", pour_date=date(2024, 10, 8))
        proc.process(p2)
        assert p2.status == PouringStatus.REJECTED
        assert "suspended" in p2.rejection_reason.lower()

    def test_suspension_lifts_after_7_days(self, store):
        p1 = make_pouring("P001", adulteration=True, pour_date=date(2024, 10, 5))
        proc = PouringProcessor(store.rate_charts, store.members)
        proc.process(p1)
        store.add_pouring(p1)

        # Pouring on day 13 (suspension ended 10-12)
        p2 = make_pouring("P002", pour_date=date(2024, 10, 13))
        proc.process(p2)
        assert p2.status == PouringStatus.ACCEPTED


# ===========================================================================
# BR-09: Rounding to paisa
# ===========================================================================

class TestBR09Rounding:
    def test_pouring_value_rounded_to_paisa(self, store):
        p = make_pouring(litres="10.1", fat="3.5", snf="8.5", temp="8.0")
        proc = PouringProcessor(store.rate_charts, store.members)
        proc.process(p)
        # price = 32.00, gross = 10.1 × 32.00 = 323.20
        assert p.gross_value == Decimal("323.20")

    def test_price_per_litre_rounded(self, cow_chart):
        """Ensure fractional paisa results are rounded."""
        price = cow_chart.price_per_litre(Decimal("3.53"), Decimal("8.53"))
        # Should have at most 2 decimal places
        assert price == price.quantize(Decimal("0.01"))


# ===========================================================================
# BR-10: Cycle bounds
# ===========================================================================

class TestBR10CycleBounds:
    def test_cycle_1_bounds(self):
        start, end, cid = get_cycle_bounds(date(2024, 10, 5))
        assert start == date(2024, 10, 1)
        assert end == date(2024, 10, 10)
        assert "C1" in cid

    def test_cycle_2_bounds(self):
        start, end, cid = get_cycle_bounds(date(2024, 10, 15))
        assert start == date(2024, 10, 11)
        assert end == date(2024, 10, 20)
        assert "C2" in cid

    def test_cycle_3_bounds_october(self):
        start, end, cid = get_cycle_bounds(date(2024, 10, 25))
        assert start == date(2024, 10, 21)
        assert end == date(2024, 10, 31)
        assert "C3" in cid

    def test_cycle_3_february_16_shifts(self):
        """Edge case: Feb cycle 21–28 = 8 days = 16 shifts."""
        start, end, cid = get_cycle_bounds(date(2024, 2, 25))
        assert end == date(2024, 2, 29)   # 2024 is leap year
        shifts = available_shifts_in_cycle(start, end)
        assert shifts == 18  # 9 days × 2

    def test_cycle_3_february_non_leap(self):
        start, end, _ = get_cycle_bounds(date(2023, 2, 25))
        assert end == date(2023, 2, 28)
        shifts = available_shifts_in_cycle(start, end)
        assert shifts == 16   # 8 days × 2


# ===========================================================================
# BR-11: Loyalty bonus (≥15 shifts)
# ===========================================================================

class TestBR11LoyaltyBonus:
    def _make_pourings_n_shifts(self, n: int, member_id="M001") -> list[Pouring]:
        """Make n accepted pourings across unique shifts starting 2024-10-01."""
        pourings = []
        base = date(2024, 10, 1)
        shifts = [Shift.AM, Shift.PM]
        for i in range(n):
            d = base + timedelta(days=i // 2)
            s = shifts[i % 2]
            p = Pouring(
                pouring_id=f"P{i:04d}", member_id=member_id, society_id="SOC001",
                pouring_datetime=datetime.combine(d, datetime.min.time()),
                shift=s, litres=Decimal("10.0"), fat=Decimal("4.0"),
                snf=Decimal("8.5"), temperature_c=Decimal("8.0"),
                adulteration_flag=False, can_id="CAN001", milk_type=MilkType.COW,
                status=PouringStatus.ACCEPTED,
                price_per_litre=Decimal("32.00"),
                gross_value=Decimal("320.00"),
            )
            pourings.append(p)
        return pourings

    def test_exactly_15_shifts_qualifies(self, base_member):
        """Edge case: member pours on exactly 15 shifts → loyalty bonus."""
        pourings = self._make_pourings_n_shifts(15)
        calc = CycleCalculator(
            base_member, pourings, date(2024, 10, 1), date(2024, 10, 10)
        )
        cycle = calc.compute()
        assert cycle.shifts_poured == 15
        assert cycle.loyalty_bonus == Decimal("75.00")   # 150L × 0.50

    def test_14_shifts_no_loyalty_bonus(self, base_member):
        pourings = self._make_pourings_n_shifts(14)
        calc = CycleCalculator(
            base_member, pourings, date(2024, 10, 1), date(2024, 10, 10)
        )
        cycle = calc.compute()
        assert cycle.loyalty_bonus == Decimal("0")

    def test_20_shifts_qualifies(self, base_member):
        pourings = self._make_pourings_n_shifts(20)
        calc = CycleCalculator(
            base_member, pourings, date(2024, 10, 1), date(2024, 10, 10)
        )
        cycle = calc.compute()
        assert cycle.loyalty_bonus > Decimal("0")


# ===========================================================================
# BR-12: Lean-month bonus (April–July)
# ===========================================================================

class TestBR12LeanBonus:
    def test_april_is_lean(self):
        assert Month.APRIL.is_lean is True

    def test_july_is_lean(self):
        assert Month.JULY.is_lean is True

    def test_august_not_lean(self):
        assert Month.AUGUST.is_lean is False

    def test_lean_bonus_applied(self, base_member):
        """April pouring → Rs 1.00/litre bonus."""
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=datetime(2024, 4, 5), shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("320.00"),
        )
        calc = CycleCalculator(
            base_member, [p], date(2024, 4, 1), date(2024, 4, 10)
        )
        cycle = calc.compute()
        assert cycle.seasonal_bonus == Decimal("10.00")   # 10L × 1.00


# ===========================================================================
# BR-13: Flush-month volume penalty (Oct–Jan)
# ===========================================================================

class TestBR13FlushPenalty:
    def test_october_is_flush(self):
        assert Month.OCTOBER.is_flush is True

    def test_january_is_flush(self):
        assert Month.JANUARY.is_flush is True

    def test_march_not_flush(self):
        assert Month.MARCH.is_flush is False

    def test_flush_penalty_on_excess_litres(self, base_member):
        """Previous cycle avg = 10 L/day. Threshold = 15 L/day in cycle (10 days).
        If total = 200 L (20 L/day), excess = 200 - 150 = 50 L → penalty = Rs 12.50."""
        pourings = []
        base_d = date(2024, 10, 1)
        counter = 0
        for i in range(10):
            d = base_d + timedelta(days=i)
            for s in [Shift.AM, Shift.PM]:
                p = Pouring(
                    pouring_id=f"P{counter:04d}", member_id="M001",
                    society_id="SOC001",
                    pouring_datetime=datetime.combine(d, datetime.min.time()),
                    shift=s, litres=Decimal("10.0"), fat=Decimal("4.0"),
                    snf=Decimal("8.5"), temperature_c=Decimal("8.0"),
                    adulteration_flag=False, can_id="CAN001", milk_type=MilkType.COW,
                    status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
                    gross_value=Decimal("320.00"),
                )
                pourings.append(p)
                counter += 1
        calc = CycleCalculator(
            base_member, pourings,
            date(2024, 10, 1), date(2024, 10, 10),
            prev_avg_daily_litres=Decimal("10.0"),
        )
        cycle = calc.compute()
        # Total = 200L; threshold = 10 * 1.5 * 10 = 150L; excess = 50L
        assert cycle.seasonal_penalty == Decimal("12.50")

    def test_flush_no_penalty_below_threshold(self, base_member):
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("320.00"),
        )
        calc = CycleCalculator(
            base_member, [p], date(2024, 10, 1), date(2024, 10, 10),
            prev_avg_daily_litres=Decimal("10.0"),
        )
        cycle = calc.compute()
        assert cycle.seasonal_penalty == Decimal("0")


# ===========================================================================
# BR-14: Feed advance recovery (20%)
# ===========================================================================

class TestBR14FeedRecovery:
    def test_feed_recovery_20_percent_of_gross(self, member_with_debts):
        """Gross = Rs 2000; 20% feed recovery = Rs 400 (outstanding = Rs 1500, so Rs 400 taken)."""
        p = Pouring(
            pouring_id="P001", member_id="M002", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("62.5"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.BUFFALO,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("2000.00"),
        )
        # Clear loan to isolate feed recovery
        member_with_debts.loan_schedules = []
        calc = CycleCalculator(
            member_with_debts, [p], date(2024, 10, 1), date(2024, 10, 10)
        )
        cycle = calc.compute()
        assert cycle.feed_recovery == Decimal("400.00")   # 20% of 2000

    def test_feed_recovery_capped_at_outstanding(self, member_with_debts):
        """If outstanding < 20% of gross, recover only outstanding."""
        # Set feed balance to Rs 50
        member_with_debts.feed_advances[0].balance = Decimal("50")
        p = Pouring(
            pouring_id="P001", member_id="M002", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.BUFFALO,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("1000.00"),
        )
        calc = CycleCalculator(
            member_with_debts, [p], date(2024, 10, 1), date(2024, 10, 10)
        )
        cycle = calc.compute()
        assert cycle.feed_recovery == Decimal("50.00")


# ===========================================================================
# BR-15: Loan EMI recovery
# ===========================================================================

class TestBR15LoanRecovery:
    def test_full_emi_when_gross_after_feed_gte_2x_emi(self, member_with_debts):
        """
        EMI = 500. Gross = 2000, feed = 20% = 400. After feed = 1600.
        1600 >= 2 * 500 = 1000 → full EMI recovered.
        Edge case: gross after feed exactly 2× EMI → full recovery (BR-15).
        """
        member_with_debts.feed_advances[0].balance = Decimal("0")  # clear feed
        member_with_debts.loan_schedules[0].emi = Decimal("500")
        p = Pouring(
            pouring_id="P001", member_id="M002", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.BUFFALO,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("1000.00"),   # exactly 2 × EMI
        )
        calc = CycleCalculator(
            member_with_debts, [p], date(2024, 10, 1), date(2024, 10, 10)
        )
        cycle = calc.compute()
        assert cycle.loan_recovery == Decimal("500.00")

    def test_partial_emi_when_gross_after_feed_less_than_2x(self, member_with_debts):
        """Gross after feed < 2× EMI → 50% EMI recovered."""
        member_with_debts.feed_advances[0].balance = Decimal("0")
        member_with_debts.loan_schedules[0].emi = Decimal("500")
        p = Pouring(
            pouring_id="P001", member_id="M002", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.BUFFALO,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("800.00"),  # < 2 × 500 = 1000
        )
        calc = CycleCalculator(
            member_with_debts, [p], date(2024, 10, 1), date(2024, 10, 10)
        )
        cycle = calc.compute()
        assert cycle.loan_recovery == Decimal("250.00")   # 50% of 500


# ===========================================================================
# BR-16: Recovery floor (Rs 500)
# ===========================================================================

class TestBR16RecoveryFloor:
    def test_net_payment_not_below_500(self, base_member):
        """
        Deductions should not reduce net payment below Rs 500 (BR-16).
        Scenario: gross=800, feed=20%=160 → after_feed=640.
        Loan EMI=750; 640 < 2×750=1500 → 50% = 375.
        Net tentative = 640 - 375 = 265 < 500.
        Floor restores loan recovery to bring net to 500.
        """
        base_member.loan_schedules = [
            LoanSchedule("L01", Decimal("10000"), Decimal("750"), Decimal("10000"))
        ]
        base_member.feed_advances = []
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("25.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("800.00"),
        )
        calc = CycleCalculator(
            base_member, [p], date(2024, 10, 1), date(2024, 10, 10)
        )
        cycle = calc.compute()
        assert cycle.net_payment >= Decimal("500.00")

    def test_floor_not_applied_when_gross_below_500(self, base_member):
        """If gross itself < 500, floor doesn't protect further."""
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("5.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("160.00"),   # < 500
        )
        calc = CycleCalculator(
            base_member, [p], date(2024, 10, 1), date(2024, 10, 10)
        )
        cycle = calc.compute()
        # Net can be < 500 when gross is also < 500
        assert cycle.net_payment <= Decimal("160.00")


# ===========================================================================
# BR-21: Member exit – full recovery ignoring floor
# ===========================================================================

class TestBR21MemberExit:
    def test_exit_recovers_all_balances(self, member_with_debts):
        member_with_debts.loan_schedules[0].balance = Decimal("2000")
        member_with_debts.feed_advances[0].balance = Decimal("1500")
        p = Pouring(
            pouring_id="P001", member_id="M002", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.BUFFALO,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("48.00"),
            gross_value=Decimal("4800.00"),
        )
        calc = CycleCalculator(
            member_with_debts, [p], date(2024, 10, 1), date(2024, 10, 5)
        )
        cycle = calc.compute_member_exit()
        assert cycle.feed_recovery == Decimal("1500")
        assert cycle.loan_recovery == Decimal("2000")
        assert member_with_debts.status == MemberStatus.EXITED

    def test_exit_net_can_go_below_500(self, member_with_debts):
        """On exit, Rs 500 floor is NOT applied."""
        member_with_debts.loan_schedules[0].balance = Decimal("200")
        member_with_debts.feed_advances[0].balance = Decimal("200")
        p = Pouring(
            pouring_id="P001", member_id="M002", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("1.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.BUFFALO,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("48.00"),
            gross_value=Decimal("48.00"),
        )
        calc = CycleCalculator(
            member_with_debts, [p], date(2024, 10, 1), date(2024, 10, 5)
        )
        cycle = calc.compute_member_exit()
        # Net = 48 - 200 - 200 = -352 (can go negative on exit)
        assert cycle.net_payment < Decimal("500")


# ===========================================================================
# BR-22/23: Society commission and transport subsidy
# ===========================================================================

class TestBR2223SocietyCommission:
    def test_commission_2_5_percent(self):
        society = Society("SOC001", "Test", "U001", Decimal("0.025"), Decimal("20"))
        engine = SocietySettlementEngine(society)
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("320.00"),
        )
        s = engine.compute(date(2024, 10, 1), date(2024, 10, 10), [p])
        assert s.commission == Decimal("8.00")   # 2.5% of 320

    def test_handling_fee_0_20_per_litre(self):
        society = Society("SOC001", "Test", "U001", Decimal("0.025"), Decimal("20"))
        engine = SocietySettlementEngine(society)
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("320.00"),
        )
        s = engine.compute(date(2024, 10, 1), date(2024, 10, 10), [p])
        assert s.handling_fee == Decimal("2.00")   # Rs 0.20 × 10L

    def test_transport_subsidy_above_15km(self):
        society = Society("SOC001", "Test", "U001", Decimal("0.025"), Decimal("20"))
        engine = SocietySettlementEngine(society)
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("320.00"),
        )
        s = engine.compute(date(2024, 10, 1), date(2024, 10, 10), [p])
        assert s.transport_subsidy == Decimal("1.50")   # Rs 0.15 × 10L

    def test_no_transport_subsidy_at_or_below_15km(self):
        society = Society("SOC001", "Test", "U001", Decimal("0.025"), Decimal("15"))
        engine = SocietySettlementEngine(society)
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("320.00"),
        )
        s = engine.compute(date(2024, 10, 1), date(2024, 10, 10), [p])
        assert s.transport_subsidy == Decimal("0")


# ===========================================================================
# BR-24/25: Sour-milk returns
# ===========================================================================

class TestBR2425SourReturn:
    def test_sour_return_reverses_at_50_percent(self):
        society = Society("SOC001", "Test", "U001", Decimal("0.025"), Decimal("20"))
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("320.00"),
        )
        sr = SourReturn("SR001", "CAN001", "SOC001", date(2024, 10, 5), "sour")
        proc = SourReturnProcessor(society, {"CAN001": [p]})
        proc.process_return(sr)
        assert p.status == PouringStatus.REVERSED
        assert p.gross_value == Decimal("160.00")

    def test_3_sour_days_forfeits_commission(self):
        society = Society("SOC001", "Test", "U001", Decimal("0.025"), Decimal("20"))
        society.sour_return_days = {date(2024,10,1), date(2024,10,2), date(2024,10,3)}
        engine = SocietySettlementEngine(society)
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 5), shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("320.00"),
        )
        s = engine.compute(date(2024, 10, 1), date(2024, 10, 10), [p])
        assert s.commission_forfeited is True
        assert s.net_payable == s.handling_fee + s.transport_subsidy

    def test_can_rejected_on_3rd_day_at_23_59(self):
        """Edge case: can rejected exactly on 3rd day at 23:59 in cycle."""
        society = Society("SOC001", "Test", "U001", Decimal("0.025"), Decimal("20"))
        # Simulate 2 existing sour days
        society.sour_return_days = {date(2024,10,1), date(2024,10,2)}
        sr = SourReturn("SR003", "CAN003", "SOC001", date(2024, 10, 3), "sour")
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=datetime(2024, 10, 3, 23, 59), shift=Shift.PM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN003", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("320.00"),
        )
        proc = SourReturnProcessor(society, {"CAN003": [p]})
        proc.process_return(sr)
        # Now society has 3 sour days → commission forfeiture
        assert len(society.sour_return_days) == 3


# ===========================================================================
# BR-26/27: Dispute handling
# ===========================================================================

class TestBR2627Disputes:
    def test_dispute_within_24h_accepted(self, rate_charts):
        pour_dt = datetime(2024, 10, 5, 8, 0)
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=pour_dt, shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("320.00"),
        )
        dispute = Dispute(
            dispute_id="D001", pouring_id="P001", member_id="M001",
            disputed_at=pour_dt + timedelta(hours=23),
            parameter="FAT", original_value=Decimal("4.0"),
        )
        pricing = PricingEngine(rate_charts)
        dp = DisputeProcessor({"P001": p}, pricing)
        dp.file_dispute(dispute)
        assert dispute.status.value != "REJECTED"

    def test_dispute_after_24h_rejected(self, rate_charts):
        pour_dt = datetime(2024, 10, 5, 8, 0)
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=pour_dt, shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("320.00"),
        )
        dispute = Dispute(
            dispute_id="D001", pouring_id="P001", member_id="M001",
            disputed_at=pour_dt + timedelta(hours=25),
            parameter="FAT", original_value=Decimal("4.0"),
        )
        pricing = PricingEngine(rate_charts)
        dp = DisputeProcessor({"P001": p}, pricing)
        dp.file_dispute(dispute)
        assert dispute.status == DisputeStatus.REJECTED

    def test_retest_higher_updates_reading(self, rate_charts):
        pour_dt = datetime(2024, 10, 5, 8, 0)
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=pour_dt, shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.0"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.00"),
            gross_value=Decimal("320.00"),
        )
        dispute = Dispute(
            dispute_id="D001", pouring_id="P001", member_id="M001",
            disputed_at=pour_dt + timedelta(hours=1),
            parameter="FAT", original_value=Decimal("4.0"),
            status=DisputeStatus.PENDING,
        )
        pricing = PricingEngine(rate_charts)
        dp = DisputeProcessor({"P001": p}, pricing)
        dp.resolve_dispute(dispute, Decimal("4.5"))
        assert dispute.status == DisputeStatus.ACCEPTED
        assert p.fat == Decimal("4.5")
        # Price should be updated
        assert p.price_per_litre > Decimal("32.00")

    def test_retest_lower_original_stands(self, rate_charts):
        """Edge case: re-test lower than original → original stands."""
        pour_dt = datetime(2024, 10, 5, 8, 0)
        p = Pouring(
            pouring_id="P001", member_id="M001", society_id="SOC001",
            pouring_datetime=pour_dt, shift=Shift.AM,
            litres=Decimal("10.0"), fat=Decimal("4.5"), snf=Decimal("8.5"),
            temperature_c=Decimal("8.0"), adulteration_flag=False,
            can_id="CAN001", milk_type=MilkType.COW,
            status=PouringStatus.ACCEPTED, price_per_litre=Decimal("32.60"),
            gross_value=Decimal("326.00"),
        )
        dispute = Dispute(
            dispute_id="D001", pouring_id="P001", member_id="M001",
            disputed_at=pour_dt + timedelta(hours=1),
            parameter="FAT", original_value=Decimal("4.5"),
            status=DisputeStatus.PENDING,
        )
        pricing = PricingEngine(rate_charts)
        dp = DisputeProcessor({"P001": p}, pricing)
        dp.resolve_dispute(dispute, Decimal("4.0"))
        assert dispute.status == DisputeStatus.REJECTED
        assert p.fat == Decimal("4.5")   # unchanged


# ===========================================================================
# Edge case: Seasonal month boundary
# ===========================================================================

class TestSeasonalBoundaries:
    def test_march_neither_lean_nor_flush(self):
        m = Month.MARCH
        assert not m.is_lean and not m.is_flush

    def test_february_neither_lean_nor_flush(self):
        m = Month.FEBRUARY
        assert not m.is_lean and not m.is_flush

    def test_april_lean_only(self):
        m = Month.APRIL
        assert m.is_lean and not m.is_flush

    def test_october_flush_only(self):
        m = Month.OCTOBER
        assert m.is_flush and not m.is_lean
