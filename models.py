from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class Union:
    union_id: str
    name: str
    chilling_centre_id: str


@dataclass
class Society:
    society_id: str
    union_id: str
    name: str
    commission_rate: Decimal
    distance_km: Decimal


@dataclass
class Member:
    member_id: str
    society_id: str
    name: str
    cattle_type: str
    feed_balance: Decimal = Decimal("0.00")
    loan_balance: Decimal = Decimal("0.00")
    emi: Decimal = Decimal("0.00")
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
    society_id: str
    date: date
    shift: str
    litres: Decimal
    fat: Decimal
    snf: Decimal
    temperature: Decimal
    adulteration: bool
    can_id: str

@dataclass
class PricedPouring:
    pouring: Pouring
    milk_type: str
    accepted: bool
    rejection_reason: str
    price_per_litre: Decimal
    value: Decimal
    quality_adjustment: Decimal
