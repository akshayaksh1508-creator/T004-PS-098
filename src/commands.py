"""
commands.py – Command-file parser and dispatcher for PS-098
Each line in the command file is a JSON object with a "command" key.
Supported commands (case-insensitive):

  REGISTER_UNION          – union_id, name, chilling_centre_id
  REGISTER_SOCIETY        – society_id, name, union_id, commission_rate, distance_km
  REGISTER_MEMBER         – member_id, name, society_id, cattle_type,
                            [loan_schedules], [feed_advances]
  REGISTER_RATE_CHART     – chart_id, milk_type, base_fat, base_snf, base_price,
                            fat_increment, snf_increment, [effective_from]
  RECORD_POURING          – pouring_id, member_id, society_id, pouring_datetime,
                            shift, litres, fat, snf, temperature_c,
                            adulteration_flag, can_id, [milk_type]
  FILE_DISPUTE            – dispute_id, pouring_id, member_id, disputed_at,
                            parameter (FAT|SNF), original_value
  RESOLVE_DISPUTE         – dispute_id, retest_value
  RECORD_SOUR_RETURN      – return_id, can_id, society_id, return_date,
                            rejection_reason
  CLOSE_CYCLE             – society_id | ALL, cycle_start, cycle_end
  EXIT_MEMBER             – member_id, exit_date
  PRINT_DAILY_REGISTER    – society_id, report_date
  PRINT_MEMBER_STATEMENT  – member_id, cycle_start, cycle_end
  PRINT_SOCIETY_SETTLEMENT– society_id, cycle_start, cycle_end

Team T004 · Python 3.10+
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from models import (
    Dispute, DisputeStatus, FeedAdvance, LoanSchedule, Member, MilkType,
    Pouring, RateChart, Shift, Society, SourReturn, Union, MemberStatus
)
from store import DataStore
from engine import (
    CycleCalculator, DisputeProcessor, PouringProcessor,
    PricingEngine, SocietySettlementEngine, SourReturnProcessor,
    get_cycle_bounds
)
from reports import (
    daily_collection_register, member_cycle_statement, society_settlement_sheet
)

logger = logging.getLogger(__name__)


def _d(val: str | None, default=None) -> Decimal | None:
    return Decimal(str(val)) if val is not None else default


def _date(val: str) -> date:
    return date.fromisoformat(val)


def _dt(val: str) -> datetime:
    return datetime.fromisoformat(val)


class CommandProcessor:
    def __init__(self, store: DataStore, output_file=sys.stdout):
        self.store = store
        self.out = output_file

    def _print(self, text: str):
        print(text, file=self.out)

    # ------------------------------------------------------------------ #
    # REGISTER commands                                                     #
    # ------------------------------------------------------------------ #

    def cmd_register_union(self, args: dict):
        u = Union(
            union_id=args["union_id"],
            name=args["name"],
            chilling_centre_id=args["chilling_centre_id"],
        )
        self.store.register_union(u)
        self._print(f"[OK] Union registered: {u.union_id} – {u.name}")

    def cmd_register_society(self, args: dict):
        s = Society(
            society_id=args["society_id"],
            name=args["name"],
            union_id=args["union_id"],
            commission_rate=_d(args.get("commission_rate", "0.025")),
            distance_km=_d(args["distance_km"]),
        )
        self.store.register_society(s)
        self._print(f"[OK] Society registered: {s.society_id} – {s.name}")

    def cmd_register_member(self, args: dict):
        loans = [
            LoanSchedule(
                loan_id=ls["loan_id"],
                principal=_d(ls["principal"]),
                emi=_d(ls["emi"]),
                balance=_d(ls.get("balance", ls["principal"])),
            )
            for ls in args.get("loan_schedules", [])
        ]
        feeds = [
            FeedAdvance(
                advance_id=fa["advance_id"],
                amount_given=_d(fa["amount_given"]),
                balance=_d(fa.get("balance", fa["amount_given"])),
            )
            for fa in args.get("feed_advances", [])
        ]
        m = Member(
            member_id=args["member_id"],
            name=args["name"],
            society_id=args["society_id"],
            cattle_type=MilkType[args["cattle_type"].upper()],
            loan_schedules=loans,
            feed_advances=feeds,
        )
        self.store.register_member(m)
        self._print(f"[OK] Member registered: {m.member_id} – {m.name}")

    def cmd_register_rate_chart(self, args: dict):
        milk_type = MilkType[args["milk_type"].upper()]
        chart = RateChart(
            chart_id=args["chart_id"],
            milk_type=milk_type,
            base_fat=_d(args["base_fat"]),
            base_snf=_d(args["base_snf"]),
            base_price=_d(args["base_price"]),
            fat_increment=_d(args["fat_increment"]),
            snf_increment=_d(args["snf_increment"]),
            effective_from=_date(args["effective_from"]) if "effective_from" in args else date.today(),
        )
        self.store.register_rate_chart(chart)
        self._print(f"[OK] Rate chart registered: {chart.chart_id} ({chart.milk_type.value})")

    # ------------------------------------------------------------------ #
    # RECORD_POURING                                                        #
    # ------------------------------------------------------------------ #

    def cmd_record_pouring(self, args: dict):
        pouring = Pouring(
            pouring_id=args["pouring_id"],
            member_id=args["member_id"],
            society_id=args["society_id"],
            pouring_datetime=_dt(args["pouring_datetime"]),
            shift=Shift[args["shift"].upper()],
            litres=_d(args["litres"]),
            fat=_d(args["fat"]),
            snf=_d(args["snf"]),
            temperature_c=_d(args["temperature_c"]),
            adulteration_flag=bool(args.get("adulteration_flag", False)),
            can_id=args["can_id"],
            milk_type=MilkType[args.get("milk_type", "COW").upper()],
        )

        processor = PouringProcessor(self.store.rate_charts, self.store.members)
        processor.process(pouring)
        self.store.add_pouring(pouring)

        status = pouring.status.value
        if pouring.status.value == "ACCEPTED":
            self._print(
                f"[POURING] {pouring.pouring_id} | {pouring.member_id} | "
                f"{pouring.shift.value} | {pouring.litres:.1f}L | "
                f"Fat={pouring.fat:.2f}% SNF={pouring.snf:.2f}% | "
                f"Price=Rs{pouring.price_per_litre:.2f}/L | "
                f"Gross=Rs{pouring.gross_value:.2f} | {status}"
            )
        else:
            self._print(
                f"[POURING] {pouring.pouring_id} | {pouring.member_id} | "
                f"{status} | {pouring.rejection_reason}"
            )

    # ------------------------------------------------------------------ #
    # DISPUTE commands                                                       #
    # ------------------------------------------------------------------ #

    def cmd_file_dispute(self, args: dict):
        dispute = Dispute(
            dispute_id=args["dispute_id"],
            pouring_id=args["pouring_id"],
            member_id=args["member_id"],
            disputed_at=_dt(args["disputed_at"]),
            parameter=args["parameter"].upper(),
            original_value=_d(args["original_value"]),
        )
        pricing = PricingEngine(self.store.rate_charts)
        dp = DisputeProcessor(self.store.pourings, pricing)
        dp.file_dispute(dispute)
        self.store.add_dispute(dispute)
        self._print(f"[DISPUTE] {dispute.dispute_id} filed: {dispute.status.value}")

    def cmd_resolve_dispute(self, args: dict):
        dispute = self.store.disputes.get(args["dispute_id"])
        if not dispute:
            self._print(f"[ERROR] Dispute {args['dispute_id']} not found")
            return
        if dispute.status == DisputeStatus.REJECTED:
            self._print(f"[DISPUTE] {dispute.dispute_id} already rejected (outside 24-h window)")
            return
        pricing = PricingEngine(self.store.rate_charts)
        dp = DisputeProcessor(self.store.pourings, pricing)
        dp.resolve_dispute(dispute, _d(args["retest_value"]))
        self._print(
            f"[DISPUTE] {dispute.dispute_id} resolved: {dispute.status.value} | "
            f"Retest={dispute.retest_value:.2f} Original={dispute.original_value:.2f}"
        )

    # ------------------------------------------------------------------ #
    # SOUR-MILK RETURN                                                       #
    # ------------------------------------------------------------------ #

    def cmd_record_sour_return(self, args: dict):
        sr = SourReturn(
            return_id=args["return_id"],
            can_id=args["can_id"],
            society_id=args["society_id"],
            return_date=_date(args["return_date"]),
            chilling_centre_rejection_reason=args.get("rejection_reason", ""),
        )
        society = self.store.societies.get(sr.society_id)
        if not society:
            self._print(f"[ERROR] Society {sr.society_id} not found")
            return
        processor = SourReturnProcessor(society, self.store.pourings_by_can)
        affected = processor.process_return(sr)
        self.store.add_sour_return(sr)
        self._print(
            f"[SOUR RETURN] Can {sr.can_id} | {len(affected)} pourings reversed | "
            f"Society {sr.society_id} has {len(society.sour_return_days)} return-day(s) this cycle"
        )

    # ------------------------------------------------------------------ #
    # CLOSE_CYCLE                                                            #
    # ------------------------------------------------------------------ #

    def cmd_close_cycle(self, args: dict):
        cycle_start = _date(args["cycle_start"])
        cycle_end = _date(args["cycle_end"])
        society_filter = args.get("society_id", "ALL")

        societies = (
            list(self.store.societies.values())
            if society_filter == "ALL"
            else [self.store.societies[society_filter]]
        )

        _, _, cycle_id = get_cycle_bounds(cycle_start)
        self._print(f"\n{'='*60}")
        self._print(f"  CYCLE CLOSE: {cycle_id} ({cycle_start} to {cycle_end})")
        self._print(f"{'='*60}")

        for society in societies:
            members_in_soc = [
                m for m in self.store.members.values()
                if m.society_id == society.society_id
                and m.status != MemberStatus.EXITED
            ]

            for member in members_in_soc:
                pourings = self.store.get_pourings_for_member_in_cycle(
                    member.member_id, cycle_start, cycle_end
                )
                # Previous cycle for flush-month calculation
                import calendar
                prev_end = cycle_start - __import__('datetime').timedelta(days=1)
                prev_start, prev_cycle_end, _ = get_cycle_bounds(prev_end)
                prev_avg = self.store.avg_daily_litres_prev_cycle(
                    member.member_id, prev_start, prev_cycle_end
                )
                calc = CycleCalculator(member, pourings, cycle_start, cycle_end, prev_avg)
                cycle = calc.compute()
                report = member_cycle_statement(member, cycle, pourings)
                self._print(report)

            # Society settlement
            soc_pourings = self.store.get_pourings_for_society_in_cycle(
                society.society_id, cycle_start, cycle_end
            )
            engine = SocietySettlementEngine(society)
            settlement = engine.compute(cycle_start, cycle_end, soc_pourings)
            self._print(society_settlement_sheet(society, settlement))
            # Reset sour_return_days for next cycle
            society.sour_return_days.clear()

    # ------------------------------------------------------------------ #
    # EXIT_MEMBER                                                            #
    # ------------------------------------------------------------------ #

    def cmd_exit_member(self, args: dict):
        member = self.store.members.get(args["member_id"])
        if not member:
            self._print(f"[ERROR] Member {args['member_id']} not found")
            return
        exit_date = _date(args["exit_date"])
        cycle_start, cycle_end, _ = get_cycle_bounds(exit_date)
        pourings = self.store.get_pourings_for_member_in_cycle(
            member.member_id, cycle_start, cycle_end
        )
        calc = CycleCalculator(member, pourings, cycle_start, exit_date)
        cycle = calc.compute_member_exit()
        self._print(f"\n[EXIT] Member {member.member_id} exited on {exit_date}")
        self._print(member_cycle_statement(member, cycle, pourings))

    # ------------------------------------------------------------------ #
    # PRINT commands                                                         #
    # ------------------------------------------------------------------ #

    def cmd_print_daily_register(self, args: dict):
        society = self.store.societies.get(args["society_id"])
        if not society:
            self._print(f"[ERROR] Society {args['society_id']} not found")
            return
        report_date = _date(args["report_date"])
        pourings = [
            p for p in self.store.pourings_by_society.get(society.society_id, [])
            if p.pour_date == report_date
        ]
        self._print(daily_collection_register(report_date, society, pourings))

    def cmd_print_member_statement(self, args: dict):
        member = self.store.members.get(args["member_id"])
        if not member:
            self._print(f"[ERROR] Member {args['member_id']} not found")
            return
        cycle_start = _date(args["cycle_start"])
        cycle_end = _date(args["cycle_end"])
        pourings = self.store.get_pourings_for_member_in_cycle(
            member.member_id, cycle_start, cycle_end
        )
        prev_end = cycle_start - __import__('datetime').timedelta(days=1)
        prev_start, prev_cycle_end, _ = get_cycle_bounds(prev_end)
        prev_avg = self.store.avg_daily_litres_prev_cycle(
            member.member_id, prev_start, prev_cycle_end
        )
        calc = CycleCalculator(member, pourings, cycle_start, cycle_end, prev_avg)
        cycle = calc.compute()
        self._print(member_cycle_statement(member, cycle, pourings))

    def cmd_print_society_settlement(self, args: dict):
        society = self.store.societies.get(args["society_id"])
        if not society:
            self._print(f"[ERROR] Society {args['society_id']} not found")
            return
        cycle_start = _date(args["cycle_start"])
        cycle_end = _date(args["cycle_end"])
        soc_pourings = self.store.get_pourings_for_society_in_cycle(
            society.society_id, cycle_start, cycle_end
        )
        engine = SocietySettlementEngine(society)
        settlement = engine.compute(cycle_start, cycle_end, soc_pourings)
        self._print(society_settlement_sheet(society, settlement))

    # ------------------------------------------------------------------ #
    # Dispatch                                                              #
    # ------------------------------------------------------------------ #

    COMMAND_MAP = {
        "register_union": cmd_register_union,
        "register_society": cmd_register_society,
        "register_member": cmd_register_member,
        "register_rate_chart": cmd_register_rate_chart,
        "record_pouring": cmd_record_pouring,
        "file_dispute": cmd_file_dispute,
        "resolve_dispute": cmd_resolve_dispute,
        "record_sour_return": cmd_record_sour_return,
        "close_cycle": cmd_close_cycle,
        "exit_member": cmd_exit_member,
        "print_daily_register": cmd_print_daily_register,
        "print_member_statement": cmd_print_member_statement,
        "print_society_settlement": cmd_print_society_settlement,
    }

    def dispatch(self, line: str, line_num: int):
        line = line.strip()
        if not line or line.startswith("#"):
            return
        try:
            args = json.loads(line)
            cmd = args.pop("command", "").lower()
            handler = self.COMMAND_MAP.get(cmd)
            if handler is None:
                self._print(f"[ERROR] Line {line_num}: Unknown command '{cmd}'")
                return
            handler(self, args)
        except json.JSONDecodeError as e:
            self._print(f"[ERROR] Line {line_num}: JSON parse error – {e}")
        except KeyError as e:
            self._print(f"[ERROR] Line {line_num}: Missing required field {e}")
        except Exception as e:
            logger.exception("Unexpected error at line %d", line_num)
            self._print(f"[ERROR] Line {line_num}: {type(e).__name__}: {e}")


def run_command_file(command_file: str | Path, output_file=sys.stdout):
    """Entry point: read a JSONL command file and process each line."""
    store = DataStore()
    processor = CommandProcessor(store, output_file)
    path = Path(command_file)
    if not path.exists():
        print(f"[FATAL] Command file not found: {path}", file=sys.stderr)
        sys.exit(1)

    with path.open(encoding="utf-8") as fh:
        for line_num, line in enumerate(fh, start=1):
            processor.dispatch(line, line_num)
