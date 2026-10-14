"""
reports.py – Report generators for PS-098 Dairy Cooperative
Produces:
  - Daily Collection Register
  - Member Cycle Statement (payment advice)
  - Society Settlement Sheet
Team T004 · Python 3.10+
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from models import (
    Member, Pouring, PouringStatus, PaymentCycle, Society,
    SocietySettlement, MilkType
)


SEP = "=" * 80


def _header(title: str) -> str:
    return f"\n{SEP}\n{title:^80}\n{SEP}"


# ---------------------------------------------------------------------------
# Daily Collection Register – BR-30
# ---------------------------------------------------------------------------

def daily_collection_register(
    report_date: date,
    society: Society,
    pourings: list[Pouring],
) -> str:
    lines = [
        _header("DAILY COLLECTION REGISTER"),
        f"  Society : {society.society_id} – {society.name}",
        f"  Date    : {report_date.strftime('%d-%b-%Y')}",
        SEP,
        f"  {'PouringID':<14} {'MemberID':<12} {'Shift':<6} {'Litres':>7} "
        f"{'Fat%':>6} {'SNF%':>6} {'Temp°C':>7} {'Price/L':>9} "
        f"{'Gross(Rs)':>11} {'Status':<12}",
        "-" * 80,
    ]

    total_litres = Decimal("0")
    total_value = Decimal("0")
    accepted_count = 0

    for p in sorted(pourings, key=lambda x: (x.shift.value, x.pouring_id)):
        status_str = p.status.value
        if p.rejection_reason:
            status_str = f"REJECTED"
        lines.append(
            f"  {p.pouring_id:<14} {p.member_id:<12} {p.shift.value:<6} "
            f"{p.litres:>7.1f} {p.fat:>6.2f} {p.snf:>6.2f} "
            f"{p.temperature_c:>7.1f} {p.price_per_litre:>9.2f} "
            f"{p.gross_value:>11.2f} {status_str:<12}"
        )
        if p.status == PouringStatus.ACCEPTED:
            total_litres += p.litres
            total_value += p.gross_value
            accepted_count += 1

    lines.append("-" * 80)
    lines.append(f"  Accepted Pourings: {accepted_count}   "
                 f"Total Litres: {total_litres:.1f}   "
                 f"Total Value: Rs {total_value:.2f}")
    lines.append(SEP)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Member Cycle Statement (Payment Advice) – BR-11 to BR-16
# ---------------------------------------------------------------------------

def member_cycle_statement(
    member: Member,
    cycle: PaymentCycle,
    pourings: list[Pouring],
) -> str:
    lines = [
        _header("MEMBER CYCLE PAYMENT ADVICE"),
        f"  Member ID   : {member.member_id}",
        f"  Name        : {member.name}",
        f"  Cycle       : {cycle.cycle_id}",
        f"  Period      : {cycle.cycle_start.strftime('%d-%b-%Y')} to "
        f"{cycle.cycle_end.strftime('%d-%b-%Y')}",
        f"  Payment Date: {cycle.payment_date.strftime('%d-%b-%Y') if cycle.payment_date else 'N/A'}",
        SEP,
        f"  {'Date':<12} {'Shift':<6} {'Litres':>7} {'Fat%':>6} {'SNF%':>6} "
        f"{'Price/L':>9} {'Gross':>10} {'Status':<12}",
        "-" * 80,
    ]

    for p in sorted(pourings, key=lambda x: (x.pour_date, x.shift.value)):
        lines.append(
            f"  {p.pour_date.strftime('%d-%b-%Y'):<12} {p.shift.value:<6} "
            f"{p.litres:>7.1f} {p.fat:>6.2f} {p.snf:>6.2f} "
            f"{p.price_per_litre:>9.2f} {p.gross_value:>10.2f} {p.status.value:<12}"
        )

    lines.append("-" * 80)
    lines.append(f"\n  SUMMARY")
    lines.append(f"  {'Total Litres':<35}: {cycle.total_litres:>10.1f}")
    lines.append(f"  {'Gross Pouring Value':<35}: Rs {cycle.gross_pouring_value:>10.2f}")
    lines.append(f"  {'Shifts Poured / Available':<35}: {cycle.shifts_poured} / {cycle.total_shifts_available}")

    if cycle.loyalty_bonus:
        lines.append(f"  {'(+) Loyalty Bonus (Rs 0.50/L)':<35}: Rs {cycle.loyalty_bonus:>10.2f}")
    if cycle.seasonal_bonus:
        lines.append(f"  {'(+) Seasonal Lean-Month Bonus':<35}: Rs {cycle.seasonal_bonus:>10.2f}")
    if cycle.seasonal_penalty:
        lines.append(f"  {'(-) Flush-Month Volume Penalty':<35}: Rs {cycle.seasonal_penalty:>10.2f}")
    if cycle.feed_recovery:
        lines.append(f"  {'(-) Feed Advance Recovery (20%)':<35}: Rs {cycle.feed_recovery:>10.2f}")
    if cycle.loan_recovery:
        lines.append(f"  {'(-) Loan EMI Recovery':<35}: Rs {cycle.loan_recovery:>10.2f}")
    if cycle.loan_balance_carried:
        lines.append(f"  {'    Loan Balance Carried Forward':<35}: Rs {cycle.loan_balance_carried:>10.2f}")

    lines.append(f"  {'-'*52}")
    lines.append(f"  {'NET PAYMENT':<35}: Rs {cycle.net_payment:>10.2f}")
    lines.append(SEP)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Society Settlement Sheet – BR-22/23/24/25
# ---------------------------------------------------------------------------

def society_settlement_sheet(
    society: Society,
    settlement: SocietySettlement,
) -> str:
    lines = [
        _header("SOCIETY SETTLEMENT SHEET"),
        f"  Society ID  : {society.society_id}",
        f"  Name        : {society.name}",
        f"  Cycle       : {settlement.cycle_id}",
        f"  Period      : {settlement.cycle_start.strftime('%d-%b-%Y')} to "
        f"{settlement.cycle_end.strftime('%d-%b-%Y')}",
        f"  Distance    : {society.distance_km} km from chilling centre",
        SEP,
        f"  Total Member Gross Pouring Value : Rs {settlement.total_member_gross:>12.2f}",
        f"  Total Litres Accepted            :    {settlement.total_litres:>12.1f}",
        f"  {'-'*55}",
        f"  Commission (2.5% of gross)       : Rs {settlement.commission:>12.2f}",
        f"  Handling Fee (Rs 0.20/litre)     : Rs {settlement.handling_fee:>12.2f}",
    ]

    if settlement.transport_subsidy:
        lines.append(f"  Transport Subsidy (Rs 0.15/L)    : Rs {settlement.transport_subsidy:>12.2f}")
    else:
        lines.append(f"  Transport Subsidy                :    {'N/A (≤15 km)':>12}")

    if settlement.commission_forfeited:
        lines.append(f"\n  *** COMMISSION FORFEITED – Sour-milk returns on ≥3 days ***")

    lines.append(f"  {'='*55}")
    lines.append(f"  NET PAYABLE TO SOCIETY           : Rs {settlement.net_payable:>12.2f}")
    lines.append(SEP)
    return "\n".join(lines)
