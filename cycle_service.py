
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


LOYALTY_MIN_SHIFTS = 15
LOYALTY_RATE = Decimal("0.50")
ZERO = Decimal("0.00")
PAISA = Decimal("0.01")


def get_cycle_dates(pour_date):
    day = pour_date.day

    if day <= 10:
        start = date(pour_date.year, pour_date.month, 1)
        end = date(pour_date.year, pour_date.month, 10)

    elif day <= 20:
        start = date(pour_date.year, pour_date.month, 11)
        end = date(pour_date.year, pour_date.month, 20)

    else:
        start = date(pour_date.year, pour_date.month, 21)

        if pour_date.month == 12:
            next_month = date(pour_date.year + 1, 1, 1)
        else:
            next_month = date(
                pour_date.year, pour_date.month + 1, 1
            )

        end = next_month - timedelta(days=1)

    return start, end


def get_payment_date(cycle_end):
    return cycle_end + timedelta(days=3)


def count_shifts(member_id, results, cycle_start, cycle_end):
    shifts = set()

    for result in results:
        pouring = result.pouring

        if result.status != "ACCEPTED":
            continue

        if pouring.member_id != member_id:
            continue

        pour_date = pouring.pour_ts.date()

        if cycle_start <= pour_date <= cycle_end:
            shifts.add((pour_date, pouring.shift))

    return len(shifts)


def calculate_accepted_litres(
    member_id, results, cycle_start, cycle_end
):
    total_litres = ZERO

    for result in results:
        pouring = result.pouring

        if result.status != "ACCEPTED":
            continue

        if pouring.member_id != member_id:
            continue

        pour_date = pouring.pour_ts.date()

        if cycle_start <= pour_date <= cycle_end:
            total_litres += Decimal(str(pouring.litres))

    return total_litres


def calculate_loyalty_bonus(shifts_poured, accepted_litres):
    if shifts_poured >= LOYALTY_MIN_SHIFTS:
        bonus = accepted_litres * LOYALTY_RATE
        return bonus.quantize(PAISA, rounding=ROUND_HALF_UP)

    return ZERO


def calculate_member_cycle_summary(
    member_id, results, cycle_start, cycle_end
):
    shifts_poured = count_shifts(
        member_id, results, cycle_start, cycle_end
    )

    accepted_litres = calculate_accepted_litres(
        member_id, results, cycle_start, cycle_end
    )

    loyalty_bonus = calculate_loyalty_bonus(
        shifts_poured, accepted_litres
    )

    return {
        "member_id": member_id,
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
        "shifts_poured": shifts_poured,
        "accepted_litres": accepted_litres,
        "loyalty_bonus": loyalty_bonus,
        "payment_date": get_payment_date(cycle_end),
    }
