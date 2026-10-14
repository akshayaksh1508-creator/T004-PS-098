"""
store.py – In-memory data store / registry for all domain objects.
Acts as the single source of truth for the running engine.
Team T004 · PS-098
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional

from models import (
    Dispute, FeedAdvance, LoanSchedule, Member, MilkType, Pouring,
    RateChart, Society, SourReturn, Union, MemberStatus
)


class DataStore:
    """Central in-memory registry. All collections keyed by their IDs."""

    def __init__(self):
        self.unions: dict[str, Union] = {}
        self.societies: dict[str, Society] = {}
        self.members: dict[str, Member] = {}
        self.rate_charts: dict[MilkType, RateChart] = {}
        self.pourings: dict[str, Pouring] = {}           # keyed by pouring_id
        self.pourings_by_can: dict[str, list[Pouring]] = {}  # keyed by can_id
        self.pourings_by_member: dict[str, list[Pouring]] = {}
        self.pourings_by_society: dict[str, list[Pouring]] = {}
        self.disputes: dict[str, Dispute] = {}
        self.sour_returns: dict[str, SourReturn] = {}
        self._pouring_counter = 0
        self._dispute_counter = 0

    # ------------------------------------------------------------------ #
    # Registration helpers                                                  #
    # ------------------------------------------------------------------ #

    def register_union(self, union: Union):
        self.unions[union.union_id] = union

    def register_society(self, society: Society):
        self.societies[society.society_id] = society

    def register_member(self, member: Member):
        self.members[member.member_id] = member
        self.pourings_by_member.setdefault(member.member_id, [])

    def register_rate_chart(self, chart: RateChart):
        key = MilkType.COW if chart.milk_type == MilkType.MIXED else chart.milk_type
        self.rate_charts[key] = chart

    # ------------------------------------------------------------------ #
    # Pouring helpers                                                       #
    # ------------------------------------------------------------------ #

    def add_pouring(self, pouring: Pouring):
        self.pourings[pouring.pouring_id] = pouring
        self.pourings_by_member.setdefault(pouring.member_id, []).append(pouring)
        self.pourings_by_society.setdefault(pouring.society_id, []).append(pouring)
        self.pourings_by_can.setdefault(pouring.can_id, []).append(pouring)

    def get_pourings_for_member_in_cycle(
        self, member_id: str, cycle_start: date, cycle_end: date
    ) -> list[Pouring]:
        return [
            p for p in self.pourings_by_member.get(member_id, [])
            if cycle_start <= p.pour_date <= cycle_end
        ]

    def get_pourings_for_society_in_cycle(
        self, society_id: str, cycle_start: date, cycle_end: date
    ) -> list[Pouring]:
        return [
            p for p in self.pourings_by_society.get(society_id, [])
            if cycle_start <= p.pour_date <= cycle_end
        ]

    # ------------------------------------------------------------------ #
    # Previous cycle average daily litres (for flush penalty)             #
    # ------------------------------------------------------------------ #

    def avg_daily_litres_prev_cycle(
        self, member_id: str, prev_cycle_start: date, prev_cycle_end: date
    ) -> Optional[Decimal]:
        """Returns avg daily litres from the previous cycle, or None if no data."""
        prev_pourings = self.get_pourings_for_member_in_cycle(
            member_id, prev_cycle_start, prev_cycle_end
        )
        accepted = [p for p in prev_pourings if p.status.value in ("ACCEPTED", "REVERSED")]
        if not accepted:
            return None
        total = sum(p.litres for p in accepted)
        days = (prev_cycle_end - prev_cycle_start).days + 1
        return total / Decimal(str(days))

    # ------------------------------------------------------------------ #
    # Dispute helpers                                                        #
    # ------------------------------------------------------------------ #

    def add_dispute(self, dispute: Dispute):
        self.disputes[dispute.dispute_id] = dispute

    def add_sour_return(self, sour_return: SourReturn):
        self.sour_returns[sour_return.return_id] = sour_return
