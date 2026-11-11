
"""Command-line integration for the PS-098 dairy procurement engine."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from can_return_service import apply_can_rejection
from cycle_service import calculate_member_cycle_summary
from dispute_service import process_retest
from file_reader import read_csv_file
from member_exit_service import calculate_member_exit_summary
from models import CanRejection, Member, Pouring, Society, Union
from pouring_service import process_pourings
from reports import (
    write_collection_register,
    write_dispute_results,
    write_member_statements,
    write_society_settlements,
)
from society_service import calculate_society_settlement


DATA_DIR = Path("T004-PS-098-sample-data")
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _decimal(value, default="0.00"):
    value = str(value).strip()
    return Decimal(value if value else default)


def _parse_date(value):
    return date.fromisoformat(str(value).strip())


def _parse_timestamp(value):
    return datetime.strptime(str(value).strip(), TIMESTAMP_FORMAT)


def _load_masters(data_dir):
    union_rows = read_csv_file(data_dir / "unions.csv")
    society_rows = read_csv_file(data_dir / "societies.csv")
    member_rows = read_csv_file(data_dir / "members.csv")

    unions = {
        row["union_id"]: Union(
            row["union_id"],
            row["union_name"],
            row["chilling_centre"],
            row["district"],
        )
        for row in union_rows
    }

    societies = {
        row["society_id"]: Society(
            row["society_id"],
            row["union_id"],
            row["society_name"],
            row["village"],
            _decimal(row["distance_km"]),
            _decimal(row["commission_pct"]),
        )
        for row in society_rows
    }

    members = {
        row["member_id"]: Member(
            member_id=row["member_id"],
            society_id=row["society_id"],
            member_name=row["member_name"],
            cattle_type=row["cattle_type"].strip().upper(),
            joined_date=_parse_date(row["joined_date"]),
            prev_cycle_litres=_decimal(row["prev_cycle_litres"]),
            feed_advance_balance=_decimal(
                row["feed_advance_balance"]
            ),
            loan_balance=_decimal(row["loan_balance"]),
            loan_emi=_decimal(row["loan_emi"]),
        )
        for row in member_rows
    }

    return unions, societies, members


def _load_pourings(data_dir):
    pourings = []

    for row in read_csv_file(data_dir / "pourings.csv"):
        pourings.append(
            Pouring(
                pouring_id=row["pouring_id"].strip(),
                member_id=row["member_id"].strip(),
                pour_ts=_parse_timestamp(row["pour_ts"]),
                shift=row["shift"].strip().upper(),
                litres=_decimal(row["litres"]),
                fat_pct=_decimal(row["fat_pct"]),
                snf_pct=_decimal(row["snf_pct"]),
                temp_c=_decimal(row["temp_c"]),
                adulteration=(
                    row["adulteration"].strip().lower() == "true"
                ),
                can_id=row["can_id"].strip(),
            )
        )

    return pourings


def _load_retests(data_dir):
    return {
        row["test_id"].strip(): row
        for row in read_csv_file(data_dir / "retests.csv")
    }


def _load_can_rejections(data_dir):
    return {
        row["rejection_id"].strip(): CanRejection(
            rejection_id=row["rejection_id"].strip(),
            can_id=row["can_id"].strip(),
            rejected_ts=_parse_timestamp(row["rejected_ts"]),
            reason=row["reason"].strip(),
        )
        for row in read_csv_file(data_dir / "can_rejections.csv")
    }


def _write_reports(
    results,
    dispute_results,
    member_summaries,
    society_settlements,
):
    write_collection_register(results)
    write_dispute_results(dispute_results)
    write_member_statements(member_summaries)
    write_society_settlements(society_settlements)


def run_commands(data_dir=DATA_DIR, commands_file=None):
    """Execute commands.txt in strict order and return final state."""

    data_dir = Path(data_dir)

    if commands_file is None:
        commands_file = data_dir / "commands.txt"
    else:
        commands_file = Path(commands_file)

    unions, societies, members = _load_masters(data_dir)
    all_pourings = _load_pourings(data_dir)
    retests = _load_retests(data_dir)
    rejection_master = _load_can_rejections(data_dir)

    pourings_by_shift = {}

    for pouring in all_pourings:
        key = (pouring.pour_ts.date(), pouring.shift)
        pourings_by_shift.setdefault(key, []).append(pouring)

    results = []
    results_by_id = {}
    dispute_results = []
    processed_rejections = []
    member_summaries = []
    society_settlements = []
    exited_members = set()

    with open(commands_file, "r", encoding="utf-8-sig") as command_file:
        for line_number, raw_line in enumerate(command_file, start=1):
            line = raw_line.strip()

            if not line or line.startswith("#"):
                continue

            parts = [part.strip() for part in line.split("|")]
            command = parts[0].upper()
            args = parts[1:]

            try:
                if command == "PROCESS_SHIFT":
                    shift_date = _parse_date(args[0])
                    shift = args[1].upper()

                    batch = pourings_by_shift.get(
                        (shift_date, shift), []
                    )

                    batch_results = process_pourings(batch, members)

                    for result in batch_results:
                        results.append(result)
                        results_by_id[
                            result.pouring.pouring_id
                        ] = result

                elif command == "DISPUTE":
                    retest = retests[args[0]]
                    pouring_id = retest["pouring_id"].strip()

                    priced_pouring = results_by_id[pouring_id]
                    member = members[
                        priced_pouring.pouring.member_id
                    ]

                    dispute_results.append(
                        process_retest(
                            retest,
                            priced_pouring,
                            member,
                        )
                    )

                elif command == "CAN_REJECT":
                    rejection = rejection_master[args[0]]

                    apply_can_rejection(
                        rejection,
                        results,
                        members,
                    )

                    processed_rejections.append(rejection)

                elif command == "MEMBER_EXIT":
                    member_id = args[0]
                    exit_date = _parse_date(args[1])

                    summary = calculate_member_exit_summary(
                        members[member_id],
                        results,
                        exit_date,
                    )

                    member_summaries.append(summary)
                    exited_members.add(member_id)

                elif command == "CLOSE_CYCLE":
                    cycle_start = _parse_date(args[0])
                    cycle_end = _parse_date(args[1])

                    for member in members.values():
                        if member.member_id in exited_members:
                            continue

                        if (
                            member.joined_date
                            and member.joined_date > cycle_end
                        ):
                            continue

                        summary = calculate_member_cycle_summary(
                            member,
                            results,
                            cycle_start,
                            cycle_end,
                        )

                        member_summaries.append(summary)

                    for society in societies.values():
                        settlement = calculate_society_settlement(
                            society,
                            members,
                            results,
                            processed_rejections,
                            cycle_start,
                            cycle_end,
                        )

                        society_settlements.append(settlement)

                elif command == "PRINT_COLLECTION_REGISTER":
                    write_collection_register(results)

                elif command == "PRINT_MEMBER_STATEMENTS":
                    write_member_statements(member_summaries)

                elif command == "PRINT_SOCIETY_SETTLEMENT":
                    write_society_settlements(society_settlements)

                else:
                    raise ValueError(
                        f"UNKNOWN_COMMAND: {command}"
                    )

            except (KeyError, IndexError, ValueError) as error:
                raise ValueError(
                    f"Command error on line {line_number}: {line}\n"
                    f"{error}"
                ) from error

    _write_reports(
        results,
        dispute_results,
        member_summaries,
        society_settlements,
    )

    return {
        "unions": unions,
        "societies": societies,
        "members": members,
        "results": results,
        "dispute_results": dispute_results,
        "can_rejections": processed_rejections,
        "member_summaries": member_summaries,
        "society_settlements": society_settlements,
    }


def main():
    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"Sample data folder not found: {DATA_DIR}. "
            "Run this program from the project root."
        )

    state = run_commands(DATA_DIR)

    print("PS-098 processing completed successfully.")
    print(f"Pourings processed: {len(state['results'])}")
    print(f"Disputes processed: {len(state['dispute_results'])}")
    print(f"Can rejections processed: {len(state['can_rejections'])}")
    print(f"Member statements: {len(state['member_summaries'])}")
    print(
        f"Society settlements: "
        f"{len(state['society_settlements'])}"
    )

    print("Generated reports:")
    print("  collection_register.csv")
    print("  member_statements.csv")
    print("  society_settlements.csv")
    print("  dispute_results.csv")


if __name__ == "__main__":
    main()
