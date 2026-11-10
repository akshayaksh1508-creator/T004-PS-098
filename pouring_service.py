
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from models import PricedPouring
from pricing import (
    calculate_base_price,
    determine_milk_type,
    get_rate_chart,
)
from validators import validate_pouring


PAISA = Decimal("0.01")
ZERO = Decimal("0.00")
LOW_SNF_LIMIT_COW = Decimal("8.0")
LOW_SNF_LIMIT_BUFFALO = Decimal("8.5")
SNF_DEDUCTION = Decimal("1.00")
TEMP_LIMIT = Decimal("10")
TEMP_DEDUCTION = Decimal("0.50")


def money(value):
    return Decimal(str(value)).quantize(
        PAISA, rounding=ROUND_HALF_UP
    )


def rejected_pouring(pouring, reason):
    return PricedPouring(
        pouring=pouring,
        fat_used=ZERO,
        snf_used=ZERO,
        chart_id="",
        chart_rate=ZERO,
        snf_deduction=ZERO,
        temp_deduction=ZERO,
        price_per_litre=ZERO,
        value=ZERO,
        status="REJECTED",
        reject_reason=reason,
    )


def process_pouring(pouring, member):
    validate_pouring(pouring)

    pour_date = pouring.pour_ts.date()

    if member.status != "ACTIVE":
        return rejected_pouring(pouring, "MEMBER_INACTIVE")

    if (
        member.suspended_until is not None
        and pour_date <= member.suspended_until
    ):
        return rejected_pouring(pouring, "MEMBER_SUSPENDED")

    fat = Decimal(str(pouring.fat_pct))
    snf = Decimal(str(pouring.snf_pct))
    temperature = Decimal(str(pouring.temp_c))
    litres = Decimal(str(pouring.litres))

    # Adulteration must trigger suspension even if fat is also low.
    if pouring.adulteration:
        member.suspended_until = pour_date + timedelta(days=7)
        return rejected_pouring(pouring, "ADULTERATION_POSITIVE")

    if fat < Decimal("3.0"):
        return rejected_pouring(pouring, "FAT_TOO_LOW")

    chart_id = determine_milk_type(fat, member.cattle_type)
    chart = get_rate_chart(chart_id)
    chart_rate = calculate_base_price(chart, fat, snf)

    if chart_id == "BUFFALO":
        snf_limit = LOW_SNF_LIMIT_BUFFALO
    else:
        snf_limit = LOW_SNF_LIMIT_COW

    if snf < snf_limit:
        snf_deduction = SNF_DEDUCTION
    else:
        snf_deduction = ZERO

    if temperature > TEMP_LIMIT:
        temp_deduction = TEMP_DEDUCTION
    else:
        temp_deduction = ZERO

    price_per_litre = money(
        chart_rate - snf_deduction - temp_deduction
    )
    value = money(litres * price_per_litre)

    return PricedPouring(
        pouring=pouring,
        fat_used=fat,
        snf_used=snf,
        chart_id=chart_id,
        chart_rate=chart_rate,
        snf_deduction=snf_deduction,
        temp_deduction=temp_deduction,
        price_per_litre=price_per_litre,
        value=value,
        status="ACCEPTED",
        reject_reason="",
    )


def process_pourings(pourings, members):
    results = []
    seen_ids = set()

    for pouring in pourings:
        if pouring.pouring_id in seen_ids:
            results.append(
                rejected_pouring(pouring, "DUPLICATE_POURING")
            )
            continue

        seen_ids.add(pouring.pouring_id)

        member = members.get(pouring.member_id)

        if member is None:
            results.append(
                rejected_pouring(pouring, "UNKNOWN_MEMBER")
            )
            continue

        try:
            results.append(process_pouring(pouring, member))
        except ValueError as error:
            results.append(
                rejected_pouring(pouring, str(error))
            )

    return results
