from datetime import datetime
from decimal import Decimal

from cycle_service import money


SOUR_REVERSAL_RATE = Decimal("0.5")
ZERO = Decimal("0.00")


def apply_can_rejection(rejection, results, members):

    if not rejection.rejection_id:
        raise ValueError("INVALID_REJECTION_ID")

    if not rejection.can_id:
        raise ValueError("INVALID_CAN_ID")

    if not isinstance(rejection.rejected_ts, datetime):
        raise ValueError("INVALID_REJECTION_TIMESTAMP")

    reversed_value = ZERO
    society_id = None
    matched = False

    for result in results:
        pouring = result.pouring

        if result.status != "ACCEPTED":
            continue

        if pouring.can_id != rejection.can_id:
            continue

        reversal = money(
            Decimal(str(result.value)) * SOUR_REVERSAL_RATE
        )
        result.sour_reversal = reversal
        reversed_value += reversal
        matched = True

        member = members.get(pouring.member_id)

        if member is not None:
            society_id = member.society_id

    if not matched:
        return None

    return {
        "rejection_id": rejection.rejection_id,
        "can_id": rejection.can_id,
        "rejected_date": rejection.rejected_ts.date(),
        "society_id": society_id,
        "reversed_value": money(reversed_value),
    }
