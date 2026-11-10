
from datetime import datetime, timedelta
from decimal import Decimal

from models import Dispute
from pouring_service import (
    LOW_SNF_LIMIT_BUFFALO,
    LOW_SNF_LIMIT_COW,
    SNF_DEDUCTION,
    TEMP_DEDUCTION,
    TEMP_LIMIT,
    money,
)
from pricing import calculate_base_price, determine_milk_type, get_rate_chart


DISPUTE_DEADLINE = timedelta(hours=24)

DISPUTE_RESULT_COLUMNS = [
    "test_id",
    "pouring_id",
    "status",
    "parameter",
    "original_value",
    "retest_value",
    "value_used",
]


def register_dispute(
    dispute_id,
    priced_pouring,
    raised_at,
    new_fat=None,
    new_snf=None,
):
    """Register a dispute within 24 hours of the original pouring."""
    if not dispute_id:
        raise ValueError("INVALID_DISPUTE_ID")

    if raised_at < priced_pouring.pouring.pour_ts:
        raise ValueError("DISPUTE_BEFORE_POURING")

    if raised_at - priced_pouring.pouring.pour_ts > DISPUTE_DEADLINE:
        raise ValueError("DISPUTE_TOO_LATE")

    if new_fat is None and new_snf is None:
        raise ValueError("NO_RETEST_READING")

    if new_fat is not None:
        new_fat = Decimal(str(new_fat))
        if new_fat <= Decimal("0"):
            raise ValueError("INVALID_RETEST_FAT")

    if new_snf is not None:
        new_snf = Decimal(str(new_snf))
        if new_snf <= Decimal("0"):
            raise ValueError("INVALID_RETEST_SNF")

    return Dispute(
        dispute_id=dispute_id,
        pouring_id=priced_pouring.pouring.pouring_id,
        raised_at=raised_at,
        new_fat=new_fat,
        new_snf=new_snf,
        status="REGISTERED",
    )


def _parse_timestamp(value):
    if isinstance(value, datetime):
        return value

    for timestamp_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ):
        try:
            return datetime.strptime(str(value), timestamp_format)
        except ValueError:
            continue

    raise ValueError("INVALID_DISPUTE_TIMESTAMP")


def _recalculate_priced_pouring(priced_pouring, member):
    """Recalculate the pouring price after a higher re-test reading."""
    pouring = priced_pouring.pouring

    fat = priced_pouring.fat_used
    snf = priced_pouring.snf_used

    chart_id = determine_milk_type(fat, member.cattle_type)
    chart = get_rate_chart(chart_id)

    chart_rate = calculate_base_price(chart, fat, snf)

    snf_limit = (
        LOW_SNF_LIMIT_BUFFALO
        if chart_id == "BUFFALO"
        else LOW_SNF_LIMIT_COW
    )

    snf_deduction = (
        SNF_DEDUCTION
        if snf < snf_limit
        else Decimal("0.00")
    )

    temp_deduction = (
        TEMP_DEDUCTION
        if Decimal(str(pouring.temp_c)) > TEMP_LIMIT
        else Decimal("0.00")
    )

    price_per_litre = money(
        chart_rate - snf_deduction - temp_deduction
    )

    value = money(
        Decimal(str(pouring.litres)) * price_per_litre
    )

    priced_pouring.chart_id = chart_id
    priced_pouring.chart_rate = chart_rate
    priced_pouring.snf_deduction = snf_deduction
    priced_pouring.temp_deduction = temp_deduction
    priced_pouring.price_per_litre = price_per_litre
    priced_pouring.value = value


def process_retest(retest_row, priced_pouring, member):
    """
    Process one re-test row from the college sample pack.

    Each row contains one parameter: FAT or SNF.
    The higher of the original and re-test readings is retained.
    """

    test_id = str(retest_row.get("test_id", "")).strip()
    pouring_id = str(retest_row.get("pouring_id", "")).strip()
    parameter = str(retest_row.get("parameter", "")).strip().upper()

    if not test_id:
        raise ValueError("INVALID_TEST_ID")

    if pouring_id != priced_pouring.pouring.pouring_id:
        raise ValueError("POURING_ID_MISMATCH")

    if parameter not in {"FAT", "SNF"}:
        raise ValueError("INVALID_RETEST_PARAMETER")

    try:
        retest_value = Decimal(
            str(retest_row.get("retest_value", ""))
        )
    except Exception as error:
        raise ValueError("INVALID_RETEST_VALUE") from error

    if not retest_value.is_finite() or retest_value <= Decimal("0"):
        raise ValueError("INVALID_RETEST_VALUE")

    dispute_ts = _parse_timestamp(
        retest_row.get("dispute_ts", "")
    )

    pour_ts = priced_pouring.pouring.pour_ts

    original_value = (
        priced_pouring.fat_used
        if parameter == "FAT"
        else priced_pouring.snf_used
    )

    if (
        dispute_ts < pour_ts
        or dispute_ts - pour_ts > DISPUTE_DEADLINE
    ):
        status = "REJECTED"
        value_used = original_value

    else:
        status = "ACCEPTED"
        value_used = max(original_value, retest_value)

        if value_used > original_value:
            if parameter == "FAT":
                priced_pouring.fat_used = value_used
            else:
                priced_pouring.snf_used = value_used

            _recalculate_priced_pouring(
                priced_pouring,
                member,
            )

    return {
        "test_id": test_id,
        "pouring_id": pouring_id,
        "status": status,
        "parameter": parameter,
        "original_value": str(original_value),
        "retest_value": str(retest_value),
        "value_used": str(value_used),
    }
