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


def format_table(headers, rows):
    str_rows = [[str(cell) for cell in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in str_rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(val))
    sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    hdr = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    lines = [sep, hdr, sep]
    for row in str_rows:
        line = "| " + " | ".join(val.ljust(widths[i]) for i, val in enumerate(row)) + " |"
        lines.append(line)
    lines.append(sep)
    return "\n".join(lines)


def print_collection_register_terminal(results, cycle_start=None, cycle_end=None):
    filtered = []
    for r in results:
        pour_date = r.pouring.pour_ts.date()
        if cycle_start and pour_date < cycle_start:
            continue
        if cycle_end and pour_date > cycle_end:
            continue
        filtered.append(r)

    headers = [
        "Pouring ID", "Member", "Timestamp", "Shift", "Litres",
        "Fat", "SNF", "Chart", "Rate", "Price/L", "Value", "Status"
    ]
    rows = []
    for r in filtered:
        rows.append([
            r.pouring.pouring_id,
            r.pouring.member_id,
            r.pouring.pour_ts.strftime("%Y-%m-%d %H:%M"),
            r.pouring.shift,
            f"{r.pouring.litres:.1f}",
            f"{r.fat_used:.2f}",
            f"{r.snf_used:.2f}",
            r.chart_id if r.chart_id else "-",
            f"{r.chart_rate:.2f}",
            f"{r.price_per_litre:.2f}",
            f"{r.value:.2f}",
            r.status if r.status == "ACCEPTED" else f"REJ ({r.reject_reason})",
        ])

    title = "COLLECTION REGISTER"
    if cycle_start and cycle_end:
        title += f" ({cycle_start} to {cycle_end})"
    print(f"\n=== {title} ===")
    print(format_table(headers, rows))


def print_member_statements_terminal(summaries, cycle_start=None, cycle_end=None):
    filtered = [
        s for s in summaries
        if (not cycle_start or s["cycle_start"] >= cycle_start)
        and (not cycle_end or s["cycle_end"] <= cycle_end)
    ]
    headers = [
        "Cycle", "Member", "Shifts", "Litres", "Pour Value",
        "Loyalty", "Lean", "Flush Pen", "Gross", "Feed Rec",
        "Loan Rec", "Net Pay", "Pay Date"
    ]
    rows = []
    for s in filtered:
        cycle_str = f"{s['cycle_start']}..{s['cycle_end']}"
        rows.append([
            cycle_str,
            s["member_id"],
            s["shifts_poured"],
            f"{s['accepted_litres']:.1f}",
            f"{s['pouring_value']:.2f}",
            f"{s['loyalty_bonus']:.2f}",
            f"{s['lean_bonus']:.2f}",
            f"{s['flush_penalty']:.2f}",
            f"{s['gross']:.2f}",
            f"{s['feed_recovery']:.2f}",
            f"{s['loan_recovery']:.2f}",
            f"{s['net_payment']:.2f}",
            str(s["payment_date"]),
        ])
    title = "MEMBER CYCLE STATEMENTS"
    if cycle_start and cycle_end:
        title += f" ({cycle_start} to {cycle_end})"
    print(f"\n=== {title} ===")
    print(format_table(headers, rows))


def print_society_settlements_terminal(settlements, cycle_start=None, cycle_end=None):
    filtered = [
        s for s in settlements
        if (not cycle_start or s["cycle_start"] >= cycle_start)
        and (not cycle_end or s["cycle_end"] <= cycle_end)
    ]
    headers = [
        "Cycle", "Society", "Litres", "Pour Value", "Commission",
        "Handling", "Forfeited?", "Subsidy", "Sour Share", "Net Settlement"
    ]
    rows = []
    for s in filtered:
        cycle_str = f"{s['cycle_start']}..{s['cycle_end']}"
        rows.append([
            cycle_str,
            s["society_id"],
            f"{s['accepted_litres']:.1f}",
            f"{s['pouring_value']:.2f}",
            f"{s['commission']:.2f}",
            f"{s['handling']:.2f}",
            "YES" if s["commission_forfeited"] else "NO",
            f"{s['transport_subsidy']:.2f}",
            f"{s['sour_milk_share']:.2f}",
            f"{s['net_settlement']:.2f}",
        ])
    title = "SOCIETY SETTLEMENTS"
    if cycle_start and cycle_end:
        title += f" ({cycle_start} to {cycle_end})"
    print(f"\n=== {title} ===")
    print(format_table(headers, rows))


def print_dispute_results_terminal(dispute_results):
    headers = ["Test ID", "Pouring ID", "Status", "Param", "Original", "Retest", "Used"]
    rows = []
    for r in dispute_results:
        rows.append([
            r["test_id"],
            r["pouring_id"],
            r["status"],
            r["parameter"],
            f"{float(r['original_value']):.2f}",
            f"{float(r['retest_value']):.2f}",
            f"{float(r['value_used']):.2f}",
        ])
    print("\n=== DISPUTE RESULTS ===")
    print(format_table(headers, rows))
