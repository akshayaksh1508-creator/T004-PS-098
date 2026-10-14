"""
engine.py – Business rule engine for PS-098 Dairy Cooperative
Implements BR-01 through BR-30 as documented in the design document.
Team T004 · Python 3.10+
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from models import (
    FeedAdvance, LoanSchedule, Member, MemberStatus, MilkType, Month,
    PaymentCycle, Pouring, PouringStatus, RateChart, Society,
    SocietySettlement, SourReturn, Dispute, DisputeStatus, Shift
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (sourced from problem statement)
# ---------------------------------------------------------------------------
FAT_MIN_ACCEPTED = Decimal("3.0")        # BR-01
FAT_COW_MAX = Decimal("5.0")             # BR-02 (≤5.0 → COW)
FAT_BUFFALO_MIN = Decimal("5.0")         # BR-02 (>5.0 → BUFFALO)

SNF_LOW_COW = Decimal("8.0")             # BR-06
SNF_LOW_BUFFALO = Decimal("8.5")         # BR-06
SNF_DEDUCTION = Decimal("1.00")          # BR-06  Rs/litre
TEMP_THRESHOLD = Decimal("10.0")         # BR-07
TEMP_DEDUCTION = Decimal("0.50")         # BR-07  Rs/litre
SUSPENSION_DAYS = 7                      # BR-08

LOYALTY_SHIFTS_REQUIRED = 15            # BR-11
LOYALTY_BONUS_RATE = Decimal("0.50")    # BR-11  Rs/litre

LEAN_BONUS = Decimal("1.00")            # BR-12  Rs/litre
FLUSH_PENALTY_RATE = Decimal("0.25")    # BR-13  Rs/litre
FLUSH_THRESHOLD_MULTIPLIER = Decimal("1.5")  # BR-13  150%

FEED_RECOVERY_RATE = Decimal("0.20")    # BR-14  20% of cycle gross
LOAN_FULL_RECOVERY_THRESHOLD = Decimal("2")  # BR-15  2× EMI
LOAN_PARTIAL_RATE = Decimal("0.50")     # BR-15
RECOVERY_FLOOR = Decimal("500.00")      # BR-16

SOCIETY_COMMISSION_RATE = Decimal("0.025")   # BR-22  2.5%
HANDLING_FEE_RATE = Decimal("0.20")          # BR-22  Rs/litre
TRANSPORT_SUBSIDY_RATE = Decimal("0.15")     # BR-23  Rs/litre
TRANSPORT_DISTANCE_THRESHOLD = Decimal("15") # BR-23  km

SOUR_RETURN_VALUE_PCT = Decimal("0.50")      # BR-24  50% refund
SOUR_RETURN_COMMISSION_LOSS_DAYS = 3         # BR-25

DISPUTE_WINDOW_HOURS = 24               # BR-26
PAISA = Decimal("0.01")


def round_paisa(value: Decimal) -> Decimal:
    """BR-09: Round to the nearest paisa (2 decimal places)."""
    return value.quantize(PAISA, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# BR-01/02/03: Milk classification and rejection
# ---------------------------------------------------------------------------

class MilkClassifier:
    """BR-01: fat < 3.0 → REJECT. BR-02: fat categorisation. BR-03: MIXED."""

    @staticmethod
    def classify(fat: Decimal, declared_type: MilkType) -> tuple[MilkType | None, str | None]:
        """
        Returns (effective_milk_type, rejection_reason).
        If rejected, effective_milk_type is None.
        """
        if fat < FAT_MIN_ACCEPTED:
            return None, f"Fat {fat}% below minimum {FAT_MIN_ACCEPTED}% (BR-01)"
        if declared_type == MilkType.MIXED:
            return MilkType.MIXED, None       # BR-03: priced on cow chart
        if fat <= FAT_COW_MAX:
            return MilkType.COW, None         # BR-02 (exactly 5.0 → COW per edge case)
        return MilkType.BUFFALO, None


# ---------------------------------------------------------------------------
# BR-04/05: Rate-chart pricing with interpolation
# ---------------------------------------------------------------------------

class PricingEngine:
    """Compute per-litre base price using the two-axis rate chart."""

    def __init__(self, rate_charts: dict[MilkType, RateChart]):
        self.charts = rate_charts

    def get_chart(self, milk_type: MilkType) -> RateChart:
        # MIXED uses COW chart (BR-03)
        key = MilkType.COW if milk_type == MilkType.MIXED else milk_type
        return self.charts[key]

    def base_price(self, milk_type: MilkType, fat: Decimal, snf: Decimal) -> Decimal:
        chart = self.get_chart(milk_type)
        return chart.price_per_litre(fat, snf)   # already rounded to paisa


# ---------------------------------------------------------------------------
# BR-06/07: Quality adjustments
# ---------------------------------------------------------------------------

class QualityAdjuster:
    @staticmethod
    def deduction_per_litre(milk_type: MilkType, snf: Decimal, temperature: Decimal) -> Decimal:
        """Returns total per-litre deduction (positive = deduction from price)."""
        total = Decimal("0")
        threshold = SNF_LOW_BUFFALO if milk_type == MilkType.BUFFALO else SNF_LOW_COW
        if snf < threshold:
            total += SNF_DEDUCTION          # BR-06
        if temperature > TEMP_THRESHOLD:
            total += TEMP_DEDUCTION         # BR-07
        return total


# ---------------------------------------------------------------------------
# Pouring processor
# ---------------------------------------------------------------------------

class PouringProcessor:
    def __init__(
        self,
        rate_charts: dict[MilkType, RateChart],
        members: dict[str, Member],
    ):
        self.pricing = PricingEngine(rate_charts)
        self.members = members

    def process(self, pouring: Pouring) -> Pouring:
        """
        Validate, classify, price a pouring in-place.
        BR-01 through BR-09 applied here.
        """
        member = self.members.get(pouring.member_id)
        if member is None:
            pouring.status = PouringStatus.REJECTED
            pouring.rejection_reason = f"Unknown member {pouring.member_id}"
            return pouring

        # BR-08: suspension check
        if member.status == MemberStatus.SUSPENDED:
            if member.suspension_end and pouring.pour_date <= member.suspension_end:
                pouring.status = PouringStatus.REJECTED
                pouring.rejection_reason = (
                    f"Member suspended until {member.suspension_end} (BR-08)"
                )
                return pouring
            else:
                # Suspension expired
                member.status = MemberStatus.ACTIVE
                member.suspension_end = None

        # BR-08: adulteration → reject pouring, suspend member 7 days
        if pouring.adulteration_flag:
            pouring.status = PouringStatus.REJECTED
            pouring.rejection_reason = "Adulteration positive (BR-08)"
            member.status = MemberStatus.SUSPENDED
            member.suspension_end = pouring.pour_date + timedelta(days=SUSPENSION_DAYS)
            logger.warning(
                "Member %s suspended until %s for adulteration on %s",
                member.member_id, member.suspension_end, pouring.pour_date,
            )
            return pouring

        # BR-01/02/03: classify milk
        effective_type, reason = MilkClassifier.classify(pouring.fat, pouring.milk_type)
        if effective_type is None:
            pouring.status = PouringStatus.REJECTED
            pouring.rejection_reason = reason
            return pouring

        # Effective milk type for pricing (MIXED → COW chart)
        pricing_type = effective_type

        # BR-04/05: base price per litre
        base = self.pricing.base_price(pricing_type, pouring.fat, pouring.snf)

        # BR-06/07: quality deductions
        deduction = QualityAdjuster.deduction_per_litre(
            pricing_type, pouring.snf, pouring.temperature_c
        )

        price = round_paisa(base - deduction)
        # Price cannot go negative
        price = max(price, Decimal("0"))

        # BR-09: pouring value = litres × price rounded to paisa
        gross = round_paisa(pouring.litres * price)

        pouring.status = PouringStatus.ACCEPTED
        pouring.price_per_litre = price
        pouring.gross_value = gross
        pouring.quality_deduction = deduction
        return pouring


# ---------------------------------------------------------------------------
# Cycle helpers
# ---------------------------------------------------------------------------

def get_cycle_bounds(d: date) -> tuple[date, date, str]:
    """
    BR-10: Returns (cycle_start, cycle_end, cycle_label) for a given date.
    Cycles: 1–10, 11–20, 21–end-of-month.
    """
    import calendar
    if d.day <= 10:
        start = d.replace(day=1)
        end = d.replace(day=10)
        label = "C1"
    elif d.day <= 20:
        start = d.replace(day=11)
        end = d.replace(day=20)
        label = "C2"
    else:
        start = d.replace(day=21)
        _, last_day = calendar.monthrange(d.year, d.month)
        end = d.replace(day=last_day)
        label = "C3"
    cycle_id = f"{d.year}-{d.month:02d}-{label}"
    return start, end, cycle_id


def available_shifts_in_cycle(cycle_start: date, cycle_end: date) -> int:
    """
    Total shifts (AM + PM) available in a cycle.
    BR-10/11: 2 shifts per day.
    Edge case: Feb cycle C3 might have only 7–8 days (16 shifts).
    """
    delta = (cycle_end - cycle_start).days + 1
    return delta * 2


# ---------------------------------------------------------------------------
# Cycle payment calculator
# ---------------------------------------------------------------------------

class CycleCalculator:
    """
    Closes a 10-day cycle for a member and computes all components.
    BR-10 through BR-16.
    """

    def __init__(
        self,
        member: Member,
        pourings: list[Pouring],
        cycle_start: date,
        cycle_end: date,
        prev_avg_daily_litres: Optional[Decimal] = None,
    ):
        self.member = member
        self.accepted = [p for p in pourings if p.status == PouringStatus.ACCEPTED]
        self.cycle_start = cycle_start
        self.cycle_end = cycle_end
        self.prev_avg = prev_avg_daily_litres

    def compute(self) -> PaymentCycle:
        _, _, cycle_id = get_cycle_bounds(self.cycle_start)
        pc = PaymentCycle(
            member_id=self.member.member_id,
            cycle_id=cycle_id,
            cycle_start=self.cycle_start,
            cycle_end=self.cycle_end,
        )

        if not self.accepted:
            pc.net_payment = Decimal("0")
            pc.closed = True
            pc.payment_date = self.cycle_end + timedelta(days=3)
            return pc

        # Aggregate
        pc.total_litres = sum(p.litres for p in self.accepted)
        pc.gross_pouring_value = sum(p.gross_value for p in self.accepted)

        # Count distinct (date, shift) pairs – BR-11
        pc.shifts_poured = len({p.shift_key for p in self.accepted})
        pc.total_shifts_available = available_shifts_in_cycle(
            self.cycle_start, self.cycle_end
        )

        # ---- Loyalty bonus – BR-11 ----
        if pc.shifts_poured >= LOYALTY_SHIFTS_REQUIRED:
            pc.loyalty_bonus = round_paisa(pc.total_litres * LOYALTY_BONUS_RATE)

        # ---- Seasonal bonus / penalty ----
        month = Month(self.cycle_start.month)
        if month.is_lean:
            # BR-12: flat Rs 1.00/litre on all accepted litres in lean months
            pc.seasonal_bonus = round_paisa(pc.total_litres * LEAN_BONUS)
        elif month.is_flush:
            # BR-13: volume penalty on litres above 150% of prev avg daily litres
            if self.prev_avg is not None:
                cycle_days = (self.cycle_end - self.cycle_start).days + 1
                threshold = round_paisa(
                    self.prev_avg * FLUSH_THRESHOLD_MULTIPLIER * cycle_days
                )
                excess = pc.total_litres - threshold
                if excess > Decimal("0"):
                    pc.seasonal_penalty = round_paisa(excess * FLUSH_PENALTY_RATE)

        gross_after_bonuses = (
            pc.gross_pouring_value
            + pc.loyalty_bonus
            + pc.seasonal_bonus
            - pc.seasonal_penalty
        )

        # ---- Feed advance recovery – BR-14 ----
        feed_deductible = round_paisa(pc.gross_pouring_value * FEED_RECOVERY_RATE)
        feed_outstanding = sum(
            fa.balance for fa in self.member.feed_advances if fa.balance > 0
        )
        actual_feed_recovery = min(feed_deductible, feed_outstanding)

        # Apply to advances (earliest first)
        remaining = actual_feed_recovery
        for fa in self.member.feed_advances:
            if fa.balance <= 0 or remaining <= 0:
                continue
            deduct = min(fa.balance, remaining)
            fa.balance -= deduct
            remaining -= deduct

        pc.feed_recovery = actual_feed_recovery
        after_feed = gross_after_bonuses - actual_feed_recovery

        # ---- Loan EMI recovery – BR-15 ----
        total_loan_recovery = Decimal("0")
        total_loan_carried = Decimal("0")

        for loan in self.member.loan_schedules:
            if loan.is_cleared():
                continue
            emi = loan.emi
            # BR-15: if gross after feed ≥ 2× EMI → full EMI; else 50%
            if after_feed >= LOAN_FULL_RECOVERY_THRESHOLD * emi:
                recovery = min(emi, loan.balance)
                carried = Decimal("0")
            else:
                half = round_paisa(emi * LOAN_PARTIAL_RATE)
                recovery = min(half, loan.balance)
                carried = emi - recovery  # balance carries forward

            loan.balance -= recovery
            total_loan_recovery += recovery
            total_loan_carried += carried

        pc.loan_recovery = total_loan_recovery
        pc.loan_balance_carried = total_loan_carried

        # ---- Recovery floor – BR-16 ----
        # "recoveries never take net payment below Rs 500 unless gross itself is lower"
        tentative_net = gross_after_bonuses - actual_feed_recovery - total_loan_recovery
        if pc.gross_pouring_value >= RECOVERY_FLOOR and tentative_net < RECOVERY_FLOOR:
            # First try to restore loan recovery
            shortfall = RECOVERY_FLOOR - tentative_net
            loan_restore = min(shortfall, total_loan_recovery)
            pc.loan_recovery = total_loan_recovery - loan_restore
            tentative_net += loan_restore
            # If still below floor after full loan restore, try feed recovery (rare)
            if tentative_net < RECOVERY_FLOOR:
                remaining_shortfall = RECOVERY_FLOOR - tentative_net
                feed_restore = min(remaining_shortfall, actual_feed_recovery)
                pc.feed_recovery = actual_feed_recovery - feed_restore
                tentative_net += feed_restore

        pc.net_payment = round_paisa(tentative_net)
        pc.closed = True
        pc.payment_date = self.cycle_end + timedelta(days=3)
        return pc

    def compute_member_exit(self) -> PaymentCycle:
        """
        BR-21: On exit, pay immediately; recover ALL outstanding balances,
        ignoring the Rs 500 floor.
        """
        _, _, cycle_id = get_cycle_bounds(self.cycle_start)
        pc = PaymentCycle(
            member_id=self.member.member_id,
            cycle_id=cycle_id + "-EXIT",
            cycle_start=self.cycle_start,
            cycle_end=self.cycle_end,
        )
        pc.total_litres = sum(p.litres for p in self.accepted)
        pc.gross_pouring_value = sum(p.gross_value for p in self.accepted)
        pc.shifts_poured = len({p.shift_key for p in self.accepted})

        # All feed outstanding
        feed_outstanding = sum(fa.balance for fa in self.member.feed_advances)
        for fa in self.member.feed_advances:
            fa.balance = Decimal("0")
        pc.feed_recovery = feed_outstanding

        # All loan outstanding
        loan_outstanding = sum(loan.balance for loan in self.member.loan_schedules)
        for loan in self.member.loan_schedules:
            loan.balance = Decimal("0")
        pc.loan_recovery = loan_outstanding

        pc.net_payment = round_paisa(
            pc.gross_pouring_value - pc.feed_recovery - pc.loan_recovery
        )
        pc.closed = True
        pc.payment_date = self.cycle_end   # immediate
        self.member.status = MemberStatus.EXITED
        return pc


# ---------------------------------------------------------------------------
# Society settlement – BR-22/23/24/25
# ---------------------------------------------------------------------------

class SocietySettlementEngine:
    def __init__(self, society: Society):
        self.society = society

    def compute(
        self,
        cycle_start: date,
        cycle_end: date,
        member_pourings: list[Pouring],
    ) -> SocietySettlement:
        _, _, cycle_id = get_cycle_bounds(cycle_start)
        s = SocietySettlement(
            society_id=self.society.society_id,
            cycle_id=cycle_id,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
        )

        accepted = [p for p in member_pourings if p.status == PouringStatus.ACCEPTED]
        s.total_litres = sum(p.litres for p in accepted)
        s.total_member_gross = sum(p.gross_value for p in accepted)

        # BR-22: commission = 2.5% of gross + Rs 0.20/litre handling
        s.commission = round_paisa(s.total_member_gross * SOCIETY_COMMISSION_RATE)
        s.handling_fee = round_paisa(s.total_litres * HANDLING_FEE_RATE)

        # BR-23: transport subsidy Rs 0.15/litre if > 15 km
        if self.society.distance_km > TRANSPORT_DISTANCE_THRESHOLD:
            s.transport_subsidy = round_paisa(s.total_litres * TRANSPORT_SUBSIDY_RATE)

        # BR-25: sour returns on ≥ 3 days → forfeit commission
        if len(self.society.sour_return_days) >= SOUR_RETURN_COMMISSION_LOSS_DAYS:
            s.commission_forfeited = True
            s.net_payable = round_paisa(s.handling_fee + s.transport_subsidy)
        else:
            s.net_payable = round_paisa(
                s.commission + s.handling_fee + s.transport_subsidy
            )

        return s


# ---------------------------------------------------------------------------
# Sour-milk return processor – BR-24
# ---------------------------------------------------------------------------

class SourReturnProcessor:
    def __init__(self, society: Society, pourings_by_can: dict[str, list[Pouring]]):
        self.society = society
        self.pourings_by_can = pourings_by_can

    def process_return(self, sour_return: SourReturn) -> list[Pouring]:
        """
        BR-24: Reverse all pourings in rejected can at 50% of value.
        BR-25: Track distinct return days.
        """
        affected = self.pourings_by_can.get(sour_return.can_id, [])
        for p in affected:
            if p.status == PouringStatus.ACCEPTED:
                p.status = PouringStatus.REVERSED
                p.gross_value = round_paisa(p.gross_value * SOUR_RETURN_VALUE_PCT)
                logger.info(
                    "Pouring %s reversed (can %s) – member bears 50%%",
                    p.pouring_id, sour_return.can_id,
                )
        # Track day for commission forfeiture check
        self.society.sour_return_days.add(sour_return.return_date)
        return affected


# ---------------------------------------------------------------------------
# Dispute processor – BR-26/27
# ---------------------------------------------------------------------------

class DisputeProcessor:
    def __init__(self, pourings: dict[str, Pouring], pricing_engine: PricingEngine):
        self.pourings = pourings
        self.pricing = pricing_engine

    def file_dispute(self, dispute: Dispute) -> Dispute:
        """BR-26: accept dispute only within 24 h of pouring."""
        pouring = self.pourings.get(dispute.pouring_id)
        if pouring is None:
            dispute.status = DisputeStatus.REJECTED
            return dispute

        window = pouring.pouring_datetime + timedelta(hours=DISPUTE_WINDOW_HOURS)
        if dispute.disputed_at > window:
            dispute.status = DisputeStatus.REJECTED
            logger.info("Dispute %s rejected – outside 24-h window (BR-26)", dispute.dispute_id)
        return dispute

    def resolve_dispute(self, dispute: Dispute, retest_value: Decimal) -> Dispute:
        """
        BR-27: Use higher of original and re-test reading.
        If re-test lower → original stands (dispute REJECTED).
        """
        dispute.retest_value = retest_value
        dispute.resolved_at = datetime.now()

        pouring = self.pourings.get(dispute.pouring_id)
        if pouring is None:
            dispute.status = DisputeStatus.REJECTED
            return dispute

        original = dispute.original_value
        if retest_value <= original:
            # BR-27: re-test lower/equal → original stands
            dispute.status = DisputeStatus.REJECTED
            logger.info(
                "Dispute %s: retest %.2f ≤ original %.2f – original stands",
                dispute.dispute_id, retest_value, original,
            )
            return dispute

        # Higher re-test → update pouring
        dispute.status = DisputeStatus.ACCEPTED
        if dispute.parameter == "FAT":
            pouring.fat = retest_value
        elif dispute.parameter == "SNF":
            pouring.snf = retest_value

        # Reprice the pouring
        effective_type, _ = MilkClassifier.classify(pouring.fat, pouring.milk_type)
        if effective_type:
            base = self.pricing.base_price(effective_type, pouring.fat, pouring.snf)
            deduction = QualityAdjuster.deduction_per_litre(
                effective_type, pouring.snf, pouring.temperature_c
            )
            pouring.price_per_litre = round_paisa(max(base - deduction, Decimal("0")))
            pouring.gross_value = round_paisa(pouring.litres * pouring.price_per_litre)

        logger.info(
            "Dispute %s accepted: %s updated to %.2f – pouring repriced",
            dispute.dispute_id, dispute.parameter, retest_value,
        )
        return dispute
