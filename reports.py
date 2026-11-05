
import csv
from collections import defaultdict
from decimal import Decimal


def write_pouring_prices(results, file_name="pouring_prices.csv"):

    fields = [
        "pouring_id",
        "member_id",
        "society_id",
        "date",
        "shift",
        "litres",
        "fat",
        "snf",
        "temperature",
        "milk_type",
        "accepted",
        "rejection_reason",
        "quality_adjustment",
        "price_per_litre",
        "value"
    ]

    with open(file_name, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for result in results:
            p = result.pouring

            writer.writerow({
                "pouring_id": p.pouring_id,
                "member_id": p.member_id,
                "society_id": p.society_id,
                "date": p.date.isoformat(),
                "shift": p.shift,
                "litres": p.litres,
                "fat": p.fat,
                "snf": p.snf,
                "temperature": p.temperature,
                "milk_type": result.milk_type,
                "accepted": result.accepted,
                "rejection_reason": result.rejection_reason,
                "quality_adjustment": result.quality_adjustment,
                "price_per_litre": result.price_per_litre,
                "value": result.value
            })


def generate_daily_collection_register(results):
    """
    Groups pouring results by date, society and milk type.
    """

    daily_data = defaultdict(lambda: {
        "total_pourings": 0,
        "accepted_pourings": 0,
        "rejected_pourings": 0,
        "received_litres": Decimal("0.0"),
        "accepted_litres": Decimal("0.0"),
        "rejected_litres": Decimal("0.0"),
        "gross_value": Decimal("0.00")
    })

    for result in results:
        p = result.pouring

        key = (
            p.date,
            p.society_id,
            result.milk_type
        )

        record = daily_data[key]

        record["total_pourings"] += 1

        record["received_litres"] += Decimal(
            str(p.litres)
        )

        if result.accepted:
            record["accepted_pourings"] += 1
            record["accepted_litres"] += Decimal(
                str(p.litres)
            )
            record["gross_value"] += result.value

        else:
            record["rejected_pourings"] += 1
            record["rejected_litres"] += Decimal(
                str(p.litres)
            )

    return daily_data


def write_daily_collection_register(
    results,
    file_name="daily_collection_register.csv"
):
    daily_data = generate_daily_collection_register(
        results
    )

    fields = [
        "date",
        "society_id",
        "milk_type",
        "total_pourings",
        "accepted_pourings",
        "rejected_pourings",
        "received_litres",
        "accepted_litres",
        "rejected_litres",
        "gross_value"
    ]

    with open(file_name, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()

        for key in sorted(daily_data):
            date, society_id, milk_type = key
            record = daily_data[key]

            writer.writerow({
                "date": date.isoformat(),
                "society_id": society_id,
                "milk_type": milk_type,
                "total_pourings": record["total_pourings"],
                "accepted_pourings": record["accepted_pourings"],
                "rejected_pourings": record["rejected_pourings"],
                "received_litres": record["received_litres"],
                "accepted_litres": record["accepted_litres"],
                "rejected_litres": record["rejected_litres"],
                "gross_value": record["gross_value"]
            })
