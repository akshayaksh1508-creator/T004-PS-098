
from datetime import timedelta
from decimal import Decimal

from models import Dispute


DISPUTE_DEADLINE = timedelta(hours=24)


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
