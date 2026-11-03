"""Small helpers for money calculations.

All money is kept as Decimal and rounded to two decimal places. Keeping this
in one file will help us use the same rounding rule in every later module.
"""

from decimal import Decimal, ROUND_HALF_UP


PAISA = Decimal("0.01")


def to_money(value: str | int | float | Decimal) -> Decimal:
    """Convert a value to rupees rounded to the nearest paisa."""

    return Decimal(str(value)).quantize(PAISA, rounding=ROUND_HALF_UP)


def multiply_money(litres: Decimal, price_per_litre: Decimal) -> Decimal:
    """Return the value of a pouring rounded to the nearest paisa."""

    return to_money(litres * price_per_litre)
