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
