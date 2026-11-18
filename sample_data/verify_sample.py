import csv
from datetime import datetime
from decimal import Decimal

from models import Member, Pouring
from pouring_service import process_pourings


BASE = r"D:\Akshay\Documents\T004-PS-098\sample_data"


def load_members():
    members = {}
    with open(BASE + r"\members.csv", "r", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            members[row["member_id"]] = Member(
                member_id=row["member_id"],
                society_id=row["society_id"],
                member_name=row["member_name"],
                cattle_type=row["cattle_type"],
                joined_date=datetime.strptime(
                    row["joined_date"], "%Y-%m-%d"
                ).date(),
                prev_cycle_litres=Decimal(row["prev_cycle_litres"]),
                feed_advance_balance=Decimal(row["feed_advance_balance"]),
                loan_balance=Decimal(row["loan_balance"]),
                loan_emi=Decimal(row["loan_emi"]),
            )
    return members


def load_pourings():
    pourings = []
    with open(BASE + r"\pourings.csv", "r", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            pourings.append(
                Pouring(
                    pouring_id=row["pouring_id"],
                    member_id=row["member_id"],
                    pour_ts=datetime.strptime(
                        row["pour_ts"], "%Y-%m-%d %H:%M:%S"
                    ),
                    shift=row["shift"],
                    litres=Decimal(row["litres"]),
                    fat_pct=Decimal(row["fat_pct"]),
                    snf_pct=Decimal(row["snf_pct"]),
                    temp_c=Decimal(row["temp_c"]),
                    adulteration=row["adulteration"] == "true",
                    can_id=row["can_id"],
                )
            )
    return pourings


members = load_members()
pourings = load_pourings()
results = process_pourings(pourings, members)

by_id = {result.pouring.pouring_id: result for result in results}

checks = [
    ("PR-00385", "chart_rate", "41.90", "EC-01 fat exactly 5.0 cow"),
    ("PR-00385", "price_per_litre", "41.90", "EC-01"),
    ("PR-01375", "chart_rate", "28.40", "EC-02 fat exactly 3.0"),
    ("PR-01449", "chart_rate", "36.05", "EC-03 snf 8.45 interpolation"),
    ("PR-00177", "value", "461.13", "12.5 x 36.89 half-up"),
    ("PR-01063", "temp_deduction", "0.00", "temp exactly 10"),
    ("PR-00668", "status", "REJECTED", "adulteration positive"),
    ("PR-00668", "reject_reason", "ADULTERATION_POSITIVE", "trap"),
    ("PR-00740", "reject_reason", "MEMBER_SUSPENDED", "suspended"),
    ("PR-00856", "reject_reason", "MEMBER_SUSPENDED", "suspended"),
    ("PR-00867", "status", "ACCEPTED", "next day after suspension"),
]

for pouring_id, field, expected, note in checks:
    result = by_id[pouring_id]
    actual = str(getattr(result, field))
    ok = "OK " if actual == expected else "FAIL"
    print(f"{ok} {pouring_id} {field} = {actual} (expected {expected}) - {note}")

print("M-004 suspended_until:", members["M-004"].suspended_until)

from main import run_commands
from pathlib import Path

state = run_commands(Path(BASE))

for s in state["member_summaries"]:
    if s["member_id"] == "M-010" and str(s["cycle_start"]) == "2026-01-11":
        actual = str(s["loyalty_bonus"])
        ok = "OK " if actual == "54.25" and s["shifts_poured"] == 15 else "FAIL"
        print(f"{ok} M-010 loyalty_bonus = {actual} (expected 54.25) - EC-04 exactly 15 shifts")

    if s["member_id"] == "M-003" and str(s["cycle_start"]) == "2026-02-21":
        actual = str(s["loyalty_bonus"])
        ok = "OK " if actual == "71.45" and s["shifts_poured"] == 15 else "FAIL"
        print(f"{ok} M-003 Feb loyalty_bonus = {actual} (expected 71.45) - EC-05 Feb 15 shifts qualifies")

    if s["member_id"] == "M-011" and str(s["cycle_start"]) == "2026-02-21":
        actual = str(s["loyalty_bonus"])
        ok = "OK " if actual == "0.00" and s["shifts_poured"] == 14 else "FAIL"
        print(f"{ok} M-011 Feb loyalty_bonus = {actual} (expected 0.00) - EC-05 Feb 14 shifts does not qualify")

    if s["member_id"] == "M-001" and str(s["cycle_start"]) == "2026-01-01":
        actual_emi = str(s["loan_recovery"])
        ok = "OK " if actual_emi == "3400.00" else "FAIL"
        print(f"{ok} M-001 loan_recovery = {actual_emi} (expected 3400.00) - EC-06 exact 2x EMI recovery")

for d in state["dispute_results"]:
    if d["test_id"] == "RT-007":
        actual = str(d["value_used"])
        ok = "OK " if actual == "4.40" else "FAIL"
        print(f"{ok} RT-007 value_used = {actual} (expected 4.40) - EC-07 retest lower than original")

for soc in state["society_settlements"]:
    if soc["society_id"] == "S-2" and str(soc["cycle_start"]) == "2026-01-11":
        ok = "OK " if soc["commission_forfeited"] is True and str(soc["commission"]) == "0.00" else "FAIL"
        print(f"{ok} S-2 commission_forfeited = {soc['commission_forfeited']} (expected True) - EC-08 3rd return at 23:59")

