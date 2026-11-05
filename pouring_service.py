
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from models import PricedPouring
from pricing import (
    determine_milk_type,
    get_rate_chart,
    calculate_base_price
)
from validators import validate_pouring


PAISA = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value):
    return Decimal(str(value)).quantize(
        PAISA,
        rounding=ROUND_HALF_UP
    )


def rejected_pouring(pouring, reason, milk_type="UNKNOWN"):
    return PricedPouring(
        pouring=pouring,
        milk_type=milk_type,
        accepted=False,
        rejection_reason=reason,
        price_per_litre=ZERO,
        value=ZERO,
        quality_adjustment=ZERO
    )


def process_pouring(pouring, member):
    """
    Validates and prices one milk pouring.
    """

    # Step 1: Validate input
    validate_pouring(pouring)

    if pouring.member_id != member.member_id:
        raise ValueError("MEMBER_MISMATCH")

    if pouring.society_id != member.society_id:
        raise ValueError("SOCIETY_MISMATCH")

    # Step 2: Check member status
    if member.status != "ACTIVE":
        return rejected_pouring(
            pouring, "MEMBER_INACTIVE"
        )

    if (
        member.suspended_until is not None
        and pouring.date <= member.suspended_until
    ):
        return rejected_pouring(
            pouring, "MEMBER_SUSPENDED"
        )

    fat = Decimal(str(pouring.fat))
    snf = Decimal(str(pouring.snf))
    temperature = Decimal(str(pouring.temperature))
    litres = Decimal(str(pouring.litres))

    # Step 3: Fat below 3.0 is rejected
    if fat < Decimal("3.0"):
        return rejected_pouring(
            pouring, "FAT_TOO_LOW"
        )

    # Step 4: Determine milk type
    milk_type = determine_milk_type(
        fat, member.cattle_type
    )

    # Step 5: Adulteration rejection
    if pouring.adulteration:
        member.suspended_until = (
            pouring.date + timedelta(days=7)
        )

        return rejected_pouring(
            pouring,
            "ADULTERATION_POSITIVE",
            milk_type
        )

    # Step 6: Get rate chart
    chart = get_rate_chart(milk_type)

    # Step 7: Calculate base price
    base_price = calculate_base_price(
        chart, fat, snf
    )

    # Step 8: Apply quality adjustments
    adjustment = ZERO

    if milk_type == "BUFFALO":
        if snf < Decimal("8.5"):
            adjustment -= Decimal("1.00")
    else:
        if snf < Decimal("8.0"):
            adjustment -= Decimal("1.00")

    if temperature > Decimal("10"):
        adjustment -= Decimal("0.50")

    # Step 9: Calculate final price per litre
    final_price = money(base_price + adjustment)

    # Step 10: Calculate pouring value
    pouring_value = money(litres * final_price)

    return PricedPouring(
        pouring=pouring,
        milk_type=milk_type,
        accepted=True,
        rejection_reason="",
        price_per_litre=final_price,
        value=pouring_value,
        quality_adjustment=adjustment
    )


def process_pourings(pourings, members):
    """
    Processes multiple pouring records.

    members must be a dictionary:
    {
        "M001": Member(...),
        "M002": Member(...)
    }
    """

    results = []
    seen_ids = set()

    for pouring in pourings:

        if pouring.pouring_id in seen_ids:
            results.append(
                rejected_pouring(
                    pouring, "DUPLICATE_POURING"
                )
            )
            continue

        seen_ids.add(pouring.pouring_id)

        member = members.get(pouring.member_id)

        if member is None:
            results.append(
                rejected_pouring(
                    pouring, "UNKNOWN_MEMBER"
                )
            )
            continue

        try:
            result = process_pouring(
                pouring, member
            )
            results.append(result)

        except ValueError as error:
            results.append(
                rejected_pouring(
                    pouring, str(error)
                )
            )

    return results
