from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass
class Union:
    union_id: str
    union_name: str
    chilling_centre: str
    district: str


@dataclass
class Society:
    society_id: str
    union_id: str
    society_name: str
    village: str
    distance_km: Decimal
    commission_pct: Decimal


@dataclass
class Member:
    member_id: str
    society_id: str
    member_name: str
    cattle_type: str
    joined_date: date | None = None
    prev_cycle_litres: Decimal = Decimal("0.0")
    feed_advance_balance: Decimal = Decimal("0.00")
    loan_balance: Decimal = Decimal("0.00")
    loan_emi: Decimal = Decimal("0.00")
    loan_carried: Decimal = Decimal("0.00")
    status: str = "ACTIVE"
    suspended_until: date | None = None


@dataclass
class RateChart:
    milk_type: str
    base_fat: Decimal
    base_snf: Decimal
    base_price: Decimal
    fat_step_price: Decimal
    snf_step_price: Decimal


@dataclass
class Pouring:
    pouring_id: str
    member_id: str
    pour_ts: datetime
    shift: str
    litres: Decimal
    fat_pct: Decimal
    snf_pct: Decimal
    temp_c: Decimal
    adulteration: bool
    can_id: str = ""


@dataclass
class PricedPouring:
    pouring: Pouring
    fat_used: Decimal
    snf_used: Decimal
    chart_id: str
    chart_rate: Decimal
    snf_deduction: Decimal
    temp_deduction: Decimal
    price_per_litre: Decimal
    value: Decimal
    status: str
    reject_reason: str
    sour_reversal: Decimal = Decimal("0.00")
