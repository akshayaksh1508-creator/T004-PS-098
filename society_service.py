from decimal import Decimal, ROUND_HALF_UP

from cycle_service import LITRE_STEP, money


HANDLING_RATE = Decimal("0.20")
SUBSIDY_RATE = Decimal("0.15")
SUBSIDY_DISTANCE_KM = Decimal("15")
FORFEIT_RETURN_DAYS = 3
ZERO = Decimal("0.00")


def calculate_society_settlement(
    society,
    members,
    results,
    can_rejections,
    cycle_start,
    cycle_end,
):

    society_id = society.society_id

    member_ids = {
        member.member_id
        for member in members.values()
        if member.society_id == society_id
    }

    accepted_litres = Decimal("0.0")
    pouring_value = ZERO
    sour_milk_share = ZERO

    for result in results:
        if result.status != "ACCEPTED":
            continue

        pouring = result.pouring

        if pouring.member_id not in member_ids:
            continue

        pour_date = pouring.pour_ts.date()

        if not (cycle_start <= pour_date <= cycle_end):
            continue

        accepted_litres += Decimal(str(pouring.litres))
        pouring_value += Decimal(str(result.value))
        sour_milk_share += Decimal(str(result.sour_reversal))

    return_days = set()

    for rejection in can_rejections:
        rejected_date = rejection.rejected_ts.date()

        if not (cycle_start <= rejected_date <= cycle_end):
            continue

        for result in results:
            if result.status != "ACCEPTED":
                continue

            if result.pouring.can_id != rejection.can_id:
                continue

            member = members.get(result.pouring.member_id)

            if (
                member is not None
                and member.society_id == society_id
            ):
                return_days.add(rejected_date)

            break

    commission_rate = (
        Decimal(str(society.commission_pct)) / 100
    )

    commission = money(pouring_value * commission_rate)
    handling = money(accepted_litres * HANDLING_RATE)

    if Decimal(str(society.distance_km)) > SUBSIDY_DISTANCE_KM:
        transport_subsidy = money(accepted_litres * SUBSIDY_RATE)
    else:
        transport_subsidy = ZERO

    commission_forfeited = (
        len(return_days) >= FORFEIT_RETURN_DAYS
    )

    if commission_forfeited:
        commission = ZERO
        handling = ZERO

    net_settlement = money(
        commission
        + handling
        + transport_subsidy
        - sour_milk_share
    )

    return {
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
        "society_id": society_id,
        "accepted_litres": accepted_litres.quantize(
            LITRE_STEP, rounding=ROUND_HALF_UP
        ),
        "pouring_value": money(pouring_value),
        "commission": commission,
        "handling": handling,
        "commission_forfeited": commission_forfeited,
        "transport_subsidy": transport_subsidy,
        "sour_milk_share": money(sour_milk_share),
        "net_settlement": net_settlement,
        "return_days": len(return_days),
    }
