"""Helpers for finding the three payment cycles in a month."""

from calendar import monthrange
from datetime import date, timedelta


def cycle_number(day: int) -> int:
    """Return 1, 2, or 3 for the cycle containing a day of the month."""

    if day < 1 or day > 31:
        raise ValueError("day must be between 1 and 31")
    if day <= 10:
        return 1
    if day <= 20:
        return 2
    return 3


def cycle_dates(year: int, month: int, cycle: int) -> tuple[date, date]:
    """Return the first and last date for one cycle."""

    if cycle not in (1, 2, 3):
        raise ValueError("cycle must be 1, 2, or 3")

    last_day = monthrange(year, month)[1]
    if cycle == 1:
        return date(year, month, 1), date(year, month, 10)
    if cycle == 2:
        return date(year, month, 11), date(year, month, 20)
    return date(year, month, 21), date(year, month, last_day)


def payment_date(year: int, month: int, cycle: int) -> date:
    """Return the third day after the cycle closes."""

    _, end_date = cycle_dates(year, month, cycle)
    return end_date + timedelta(days=3)
