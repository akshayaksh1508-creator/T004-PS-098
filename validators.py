from decimal import Decimal


def is_valid_shift(shift):
    return shift in ("AM", "PM")


def is_valid_litres(litres):
    value = Decimal(str(litres))
    return value > 0 and value * 10 == value * 10 // 1


def is_valid_cattle_type(cattle_type):
    return cattle_type in ("COW", "BUFFALO", "MIXED")
