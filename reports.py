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


DISPUTE_RESULT_COLUMNS = [
    "test_id",
    "pouring_id",
    "status",
    "parameter",
    "original_value",
    "retest_value",
    "value_used",
]


MEMBER_STATEMENT_COLUMNS = [
    "cycle_start",
    "cycle_end",
    "member_id",
    "shifts_poured",
    "accepted_litres",
    "pouring_value",
    "sour_reversal",
    "loyalty_bonus",
    "lean_bonus",
    "flush_penalty",
    "gross",
    "feed_recovery",
    "loan_recovery",
    "loan_carried",
    "net_payment",
    "payment_date",
    "feed_balance_after",
    "loan_balance_after",
]


SOCIETY_SETTLEMENT_COLUMNS = [
    "cycle_start",
    "cycle_end",
    "society_id",
    "accepted_litres",
    "pouring_value",
    "commission",
    "handling",
    "commission_forfeited",
    "transport_subsidy",
    "sour_milk_share",
    "net_settlement",
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


def write_dispute_results(
    results, file_name="dispute_results.csv"
):

    with open(file_name, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=DISPUTE_RESULT_COLUMNS,
            extrasaction="raise",
        )
        writer.writeheader()

        for result in results:
            writer.writerow({
                column: result[column]
                for column in DISPUTE_RESULT_COLUMNS
            })


def write_member_statements(
    summaries, file_name="member_statements.csv"
):

    sorted_summaries = sorted(
        summaries,
        key=lambda summary: (
            summary["member_id"],
            summary["cycle_start"],
        ),
    )

    with open(file_name, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=MEMBER_STATEMENT_COLUMNS,
            extrasaction="raise",
        )
        writer.writeheader()

        for summary in sorted_summaries:
            writer.writerow({
                column: summary[column]
                for column in MEMBER_STATEMENT_COLUMNS
            })


def write_society_settlements(
    settlements, file_name="society_settlements.csv"
):

    sorted_settlements = sorted(
        settlements,
        key=lambda settlement: (
            settlement["society_id"],
            settlement["cycle_start"],
        ),
    )

    with open(file_name, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=SOCIETY_SETTLEMENT_COLUMNS,
            extrasaction="raise",
        )
        writer.writeheader()

        for settlement in sorted_settlements:
            writer.writerow({
                column: (
                    "true" if settlement[column] is True
                    else "false" if settlement[column] is False
                    else settlement[column]
                )
                for column in SOCIETY_SETTLEMENT_COLUMNS
            })
