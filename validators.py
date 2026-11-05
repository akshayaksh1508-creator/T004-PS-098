
from decimal import Decimal, InvalidOperation
from datetime import date


def is_valid_shift(shift):
    return shift in ("AM", "PM")


def is_valid_litres(litres):
    try:
        value = Decimal(str(litres))
        return (
            value > 0
            and value * 10 == (value * 10).to_integral_value()
        )
    except (InvalidOperation, ValueError):
        return False


def is_valid_cattle_type(cattle_type):
    return str(cattle_type).upper() in (
        "COW", "BUFFALO", "MIXED"
    )


def is_valid_decimal(value):
    try:
        number = Decimal(str(value))
        return number.is_finite() and number >= 0
    except (InvalidOperation, ValueError):
        return False


def validate_pouring(pouring):
    if not pouring.pouring_id:
        raise ValueError("INVALID_POURING_ID")

    if not pouring.member_id:
        raise ValueError("INVALID_MEMBER_ID")

    if not pouring.society_id:
        raise ValueError("INVALID_SOCIETY_ID")

    if not isinstance(pouring.date, date):
        raise ValueError("INVALID_DATE")

    if not is_valid_shift(pouring.shift):
        raise ValueError("INVALID_SHIFT")

    if not is_valid_litres(pouring.litres):
        raise ValueError("INVALID_LITRES")

    if not is_valid_decimal(pouring.fat):
        raise ValueError("INVALID_FAT")

    if not is_valid_decimal(pouring.snf):
        raise ValueError("INVALID_SNF")

    if not is_valid_decimal(pouring.temperature):
        raise ValueError("INVALID_TEMPERATURE")

    if not isinstance(pouring.adulteration, bool):
        raise ValueError("INVALID_ADULTERATION_FLAG")

    if not pouring.can_id:
        raise ValueError("INVALID_CAN_ID")

    return True
