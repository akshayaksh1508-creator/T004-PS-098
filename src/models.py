"""
models.py – Domain entities for the Dairy Cooperative Milk Procurement Engine
PS-098 · Team T004
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class MilkType(str, Enum):
    COW = "COW"
    BUFFALO = "BUFFALO"
    MIXED = "MIXED"   # declared by member; priced on cow chart


class Shift(str, Enum):
    AM = "AM"
    PM = "PM"


class PouringStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    REVERSED = "REVERSED"   # sour-milk can return (50 % of value)


class MemberStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"  # adulteration ban (7 days)
    EXITED = "EXITED"


class DisputeStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"   # re-test recorded, higher value used
    REJECTED = "REJECTED"   # after 24 h or re-test lower


class Month(int, Enum):
    """Used for seasonal bonus classification."""
    JANUARY = 1
    FEBRUARY = 2
    MARCH = 3
    APRIL = 4
    MAY = 5
    JUNE = 6
    JULY = 7
    AUGUST = 8
    SEPTEMBER = 9
    OCTOBER = 10
    NOVEMBER = 11
    DECEMBER = 12

    @property
    def is_lean(self) -> bool:
        """BR-19: April–July are lean months."""
        return self.value in (4, 5, 6, 7)

    @property
    def is_flush(self) -> bool:
        """BR-20: October–January are flush months."""
        return self.value in (10, 11, 12, 1)


# ---------------------------------------------------------------------------
# Rate Chart
# ---------------------------------------------------------------------------

@dataclass
class RateChart:
    """
    Two-axis rate chart keyed on (fat_percent, snf_percent).
    BR-04: fat steps 0.1, SNF steps 0.1; linear interpolation on both axes.
    """
    chart_id: str
    milk_type: MilkType          # COW or BUFFALO (MIXED uses COW chart)
    base_fat: Decimal            # reference fat %
    base_snf: Decimal            # reference SNF %
    base_price: Decimal          # Rs per litre at base
    fat_increment: Decimal       # Rs per 0.1 fat above base
    snf_increment: Decimal       # Rs per 0.1 SNF above base
    effective_from: date = field(default_factory=date.today)

    def price_per_litre(self, fat: Decimal, snf: Decimal) -> Decimal:
        """
        BR-04 / BR-05: bi-linear interpolation.
        price = base + (fat − base_fat)/0.1 * fat_increment
                     + (snf − base_snf)/0.1 * snf_increment
        """
        fat_units = (fat - self.base_fat) / Decimal("0.1")
        snf_units = (snf - self.base_snf) / Decimal("0.1")
        raw = self.base_price + fat_units * self.fat_increment + snf_units * self.snf_increment
        # Round to paisa (2 decimal places) – BR-09
        return raw.quantize(Decimal("0.01"))


# ---------------------------------------------------------------------------
# Loan / Feed advance
# ---------------------------------------------------------------------------

@dataclass
class LoanSchedule:
    loan_id: str
    principal: Decimal
    emi: Decimal                 # monthly EMI amount
    balance: Decimal             # outstanding balance

    def is_cleared(self) -> bool:
        return self.balance <= Decimal("0")


@dataclass
class FeedAdvance:
    advance_id: str
    amount_given: Decimal
    balance: Decimal             # outstanding


# ---------------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------------

@dataclass
class Union:
    union_id: str
    name: str
    chilling_centre_id: str


@dataclass
class Society:
    """BR-23–25: commission, transport subsidy, sour-milk return tracking."""
    society_id: str
    name: str
    union_id: str
    commission_rate: Decimal     # e.g. Decimal("0.025") for 2.5 %
    distance_km: Decimal         # distance to chilling centre
    # Runtime state
    sour_return_days: set = field(default_factory=set)   # set of dates with returns in current cycle


@dataclass
class Member:
    member_id: str
    name: str
    society_id: str
    cattle_type: MilkType        # declared type; COW/BUFFALO/MIXED
    loan_schedules: list[LoanSchedule] = field(default_factory=list)
    feed_advances: list[FeedAdvance] = field(default_factory=list)
    status: MemberStatus = MemberStatus.ACTIVE
    suspension_end: Optional[date] = None      # BR-08


# ---------------------------------------------------------------------------
# Pouring
# ---------------------------------------------------------------------------

@dataclass
class Pouring:
    pouring_id: str
    member_id: str
    society_id: str
    pouring_datetime: datetime
    shift: Shift
    litres: Decimal              # measured to 0.1
    fat: Decimal
    snf: Decimal
    temperature_c: Decimal       # ambient temperature at receipt
    adulteration_flag: bool
    can_id: str
    milk_type: MilkType

    # Computed fields (filled by engine)
    status: PouringStatus = PouringStatus.ACCEPTED
    price_per_litre: Decimal = Decimal("0")
    gross_value: Decimal = Decimal("0")
    quality_deduction: Decimal = Decimal("0")  # total per-litre deduction applied
    rejection_reason: Optional[str] = None

    @property
    def pour_date(self) -> date:
        return self.pouring_datetime.date()

    @property
    def shift_key(self) -> tuple:
        """Unique (date, shift) identifier."""
        return (self.pour_date, self.shift)


# ---------------------------------------------------------------------------
# Dispute
# ---------------------------------------------------------------------------

@dataclass
class Dispute:
    dispute_id: str
    pouring_id: str
    member_id: str
    disputed_at: datetime
    parameter: str               # "FAT" or "SNF"
    original_value: Decimal
    retest_value: Optional[Decimal] = None
    status: DisputeStatus = DisputeStatus.PENDING
    resolved_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Sour-milk return (can-level)
# ---------------------------------------------------------------------------

@dataclass
class SourReturn:
    return_id: str
    can_id: str
    society_id: str
    return_date: date
    chilling_centre_rejection_reason: str


# ---------------------------------------------------------------------------
# Payment cycle
# ---------------------------------------------------------------------------

@dataclass
class PaymentCycle:
    """Represents a 10-day billing cycle for a member."""
    member_id: str
    cycle_id: str                # e.g. "2024-10-C1" for days 1-10 of Oct 2024
    cycle_start: date
    cycle_end: date

    total_litres: Decimal = Decimal("0")
    gross_pouring_value: Decimal = Decimal("0")
    shifts_poured: int = 0
    total_shifts_available: int = 0

    loyalty_bonus: Decimal = Decimal("0")
    seasonal_bonus: Decimal = Decimal("0")
    seasonal_penalty: Decimal = Decimal("0")

    feed_recovery: Decimal = Decimal("0")
    loan_recovery: Decimal = Decimal("0")
    loan_balance_carried: Decimal = Decimal("0")

    net_payment: Decimal = Decimal("0")
    payment_date: Optional[date] = None   # 3rd day after cycle close

    closed: bool = False


@dataclass
class SocietySettlement:
    society_id: str
    cycle_id: str
    cycle_start: date
    cycle_end: date

    total_member_gross: Decimal = Decimal("0")
    total_litres: Decimal = Decimal("0")

    commission: Decimal = Decimal("0")      # 2.5% of gross
    handling_fee: Decimal = Decimal("0")    # Rs 0.20/litre
    transport_subsidy: Decimal = Decimal("0")  # Rs 0.15/litre if >15 km
    commission_forfeited: bool = False       # sour-milk returns ≥3 days

    net_payable: Decimal = Decimal("0")
