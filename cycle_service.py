from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


LOYALTY_MIN_SHIFTS = 15
LOYALTY_RATE = Decimal("0.50")
LEAN_MONTHS = {4, 5, 6, 7}
LEAN_RATE = Decimal("1.00")
FLUSH_MONTHS = {10, 11, 12, 1}
FLUSH_RATE = Decimal("0.25")
FLUSH_MULTIPLIER = Decimal("1.5")
FEED_RATE = Decimal("0.20")
EMI_MULTIPLE = 2
PAYMENT_FLOOR = Decimal("500.00")
ZERO = Decimal("0.00")
PAISA = Decimal("0.01")
LITRE_STEP = Decimal("0.1")


def money(value):
    return Decimal(str(value)).quantize(PAISA, rounding=ROUND_HALF_UP)


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


def accepted_cycle_results(member_id, results, cycle_start, cycle_end):
    for result in results:
        if result.status != "ACCEPTED":
            continue

        pouring = result.pouring

        if pouring.member_id != member_id:
            continue

        pour_date = pouring.pour_ts.date()

        if cycle_start <= pour_date <= cycle_end:
            yield result


def count_shifts(member_id, results, cycle_start, cycle_end):
    shifts = set()

    for result in accepted_cycle_results(
        member_id, results, cycle_start, cycle_end
    ):
        pouring = result.pouring
        shifts.add((pouring.pour_ts.date(), pouring.shift))

    return len(shifts)


def calculate_accepted_litres(
    member_id, results, cycle_start, cycle_end
):
    total_litres = Decimal("0.0")

    for result in accepted_cycle_results(
        member_id, results, cycle_start, cycle_end
    ):
        total_litres += Decimal(str(result.pouring.litres))

    return total_litres.quantize(LITRE_STEP, rounding=ROUND_HALF_UP)


def calculate_cycle_value(
    member_id, results, cycle_start, cycle_end
):
    pouring_value = ZERO
    sour_reversal = ZERO

    for result in accepted_cycle_results(
        member_id, results, cycle_start, cycle_end
    ):
        pouring_value += Decimal(str(result.value))
        sour_reversal += Decimal(str(result.sour_reversal))

    return money(pouring_value), money(sour_reversal)


def daily_litres_by_date(
    member_id, results, cycle_start, cycle_end
):
    daily = {}

    for result in accepted_cycle_results(
        member_id, results, cycle_start, cycle_end
    ):
        pouring = result.pouring
        pour_date = pouring.pour_ts.date()
        daily[pour_date] = (
            daily.get(pour_date, ZERO)
            + Decimal(str(pouring.litres))
        )

    return daily


def calculate_loyalty_bonus(shifts_poured, accepted_litres):
    if shifts_poured >= LOYALTY_MIN_SHIFTS:
        return money(accepted_litres * LOYALTY_RATE)

    return ZERO


def calculate_lean_bonus(cycle_start, accepted_litres):
    if cycle_start.month in LEAN_MONTHS:
        return money(accepted_litres * LEAN_RATE)

    return ZERO


def previous_cycle_days(cycle_start):
    previous_end = cycle_start - timedelta(days=1)
    previous_start, _ = get_cycle_dates(previous_end)
    return (previous_end - previous_start).days + 1


def calculate_flush_threshold(cycle_start, prev_cycle_litres):
    average = (
        Decimal(str(prev_cycle_litres))
        / previous_cycle_days(cycle_start)
    )
    threshold = FLUSH_MULTIPLIER * average
    return threshold.quantize(LITRE_STEP, rounding=ROUND_HALF_UP)


def calculate_flush_penalty(daily_litres, threshold):
    excess = ZERO

    for litres in daily_litres.values():
        above = litres - threshold

        if above > 0:
            excess += above

    return money(excess * FLUSH_RATE)


def calculate_recoveries(
    gross, feed_balance, loan_balance, loan_emi,
    loan_carried=ZERO,
):
    gross = money(gross)
    feed_recovery = min(
        money(feed_balance), money(gross * FEED_RATE)
    )
    loan_due = min(
        money(loan_emi + loan_carried), money(loan_balance)
    )

    if money(gross - feed_recovery) >= EMI_MULTIPLE * loan_due:
        loan_recovery = loan_due
    else:
        loan_recovery = money(loan_due / 2)

    if gross < PAYMENT_FLOOR:
        feed_recovery = ZERO
        loan_recovery = ZERO

    net = money(gross - feed_recovery - loan_recovery)

    if gross >= PAYMENT_FLOOR and net < PAYMENT_FLOOR:
        shortage = PAYMENT_FLOOR - net
        loan_cut = min(loan_recovery, shortage)
        loan_recovery = money(loan_recovery - loan_cut)
        shortage -= loan_cut

        if shortage > 0:
            feed_recovery = money(
                feed_recovery - min(feed_recovery, shortage)
            )

        net = PAYMENT_FLOOR

    return {
        "feed_recovery": money(feed_recovery),
        "loan_recovery": money(loan_recovery),
        "loan_carried": money(loan_due - loan_recovery),
        "feed_balance_after": money(feed_balance - feed_recovery),
        "loan_balance_after": money(loan_balance - loan_recovery),
        "net_payment": net,
    }


def calculate_member_cycle_summary(
    member, results, cycle_start, cycle_end
):
    shifts_poured = count_shifts(
        member.member_id, results, cycle_start, cycle_end
    )

    accepted_litres = calculate_accepted_litres(
        member.member_id, results, cycle_start, cycle_end
    )

    pouring_value, sour_reversal = calculate_cycle_value(
        member.member_id, results, cycle_start, cycle_end
    )

    loyalty_bonus = calculate_loyalty_bonus(
        shifts_poured, accepted_litres
    )

    lean_bonus = calculate_lean_bonus(cycle_start, accepted_litres)

    flush_penalty = ZERO

    if cycle_start.month in FLUSH_MONTHS:
        daily_litres = daily_litres_by_date(
            member.member_id, results, cycle_start, cycle_end
        )
        threshold = calculate_flush_threshold(
            cycle_start, member.prev_cycle_litres
        )
        flush_penalty = calculate_flush_penalty(
            daily_litres, threshold
        )

    gross = money(
        pouring_value
        - sour_reversal
        + loyalty_bonus
        + lean_bonus
        - flush_penalty
    )

    recovery = calculate_recoveries(
        gross,
        member.feed_advance_balance,
        member.loan_balance,
        member.loan_emi,
        member.loan_carried,
    )

    member.feed_advance_balance = recovery["feed_balance_after"]
    member.loan_balance = recovery["loan_balance_after"]
    member.loan_carried = recovery["loan_carried"]
    member.prev_cycle_litres = accepted_litres

    return {
        "cycle_start": cycle_start,
        "cycle_end": cycle_end,
        "member_id": member.member_id,
        "shifts_poured": shifts_poured,
        "accepted_litres": accepted_litres,
        "pouring_value": pouring_value,
        "sour_reversal": sour_reversal,
        "loyalty_bonus": loyalty_bonus,
        "lean_bonus": lean_bonus,
        "flush_penalty": flush_penalty,
        "gross": gross,
        "feed_recovery": recovery["feed_recovery"],
        "loan_recovery": recovery["loan_recovery"],
        "loan_carried": recovery["loan_carried"],
        "net_payment": recovery["net_payment"],
        "payment_date": get_payment_date(cycle_end),
        "feed_balance_after": recovery["feed_balance_after"],
        "loan_balance_after": recovery["loan_balance_after"],
    }
