import csv


REGISTER_COLUMNS = [
    "pouring_id",
    "member_id",
    "pour_ts",
    "shift",
    "litres",
    "fat_used",
    "snf_used",
    "chart_id",
    "chart_rate",
    "snf_deduction",
    "temp_deduction",
    "price_per_litre",
    "value",
    "status",
    "reject_reason",
    "sour_reversal",
]


def write_collection_register(
    results, file_name="collection_register.csv"
):
    sorted_results = sorted(
        results, key=lambda result: result.pouring.pouring_id
    )

    with open(file_name, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=REGISTER_COLUMNS)
        writer.writeheader()

        for result in sorted_results:
            pouring = result.pouring

            writer.writerow({
                "pouring_id": pouring.pouring_id,
                "member_id": pouring.member_id,
                "pour_ts": pouring.pour_ts.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "shift": pouring.shift,
                "litres": pouring.litres,
                "fat_used": result.fat_used,
                "snf_used": result.snf_used,
                "chart_id": result.chart_id,
                "chart_rate": result.chart_rate,
                "snf_deduction": result.snf_deduction,
                "temp_deduction": result.temp_deduction,
                "price_per_litre": result.price_per_litre,
                "value": result.value,
                "status": result.status,
                "reject_reason": result.reject_reason,
                "sour_reversal": result.sour_reversal,
            })
