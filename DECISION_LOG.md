# Decision Log: PS-098 Dairy Milk Procurement Engine

**Team ID:** T004  
**Project:** PS-098 · Dairy Cooperative Milk Procurement Pricing and Member Payment Engine  
**Authors:** Akshatha B & Akshay H  
**Last Updated:** November 2026  

This document logs all key architectural, technical, mathematical, and business policy decisions made during the design, development, and refinement of the PS-098 procurement engine.

---

## 1. Architecture & Technology Decisions

### ADR-01: Programming Language & Standard Library Only
- **Decision:** Use Python 3.10+ using **strictly the Python Standard Library** (`decimal`, `datetime`, `csv`, `pathlib`, `dataclasses`, `unittest`).
- **Context:** The brief permitted Java 17+ or Python 3.10+.
- **Rationale:** 
  - Zero external dependencies (`pip` install free) guarantees portability across any evaluator environment.
  - Built-in `decimal` module provides arbitrary-precision base-10 financial math required for audit compliance.
- **Consequences:** We wrote a custom ASCII table formatter (`format_table`) and custom CSV streaming readers instead of importing third-party libraries like `pandas` or `tabulate`.

### ADR-02: Command-Stream CLI Interface vs. Web / Database Framework
- **Decision:** Build a deterministic batch command-driven engine reading `commands.txt` without a database server or web UI.
- **Context:** The assignment specification explicitly states: *"Command-file driven; no UI"*.
- **Rationale:** 
  - Village Dairy Cooperative Societies (VDCS) operate in rural environments where batch data sync (commands and files) is standard practice.
  - File-to-file processing makes the engine completely deterministic, reproducible, auditable, and easily testable.
- **Consequences:** State is held in-memory during the command stream execution and flushed to disk on explicit `PRINT_*` commands and cycle closures.

### ADR-03: Domain Modeling via Data Classes
- **Decision:** Represent domain entities (`Union`, `Society`, `Member`, `Pouring`, `PricedPouring`, `RateChart`, `Dispute`, `CanRejection`) as `@dataclass` objects in `models.py`.
- **Rationale:** Clear type annotations, clean data manipulation, immutability where appropriate, and clean separation of concerns from calculation services.

---

## 2. Mathematical & Pricing Decisions

### ADR-04: Exact Base-10 Arithmetic (`Decimal`) vs Binary Floating-Point (`float`)
- **Decision:** Disallow Python's built-in `float` for all monetary, volume, and percentage calculations. Use `Decimal` with explicit `ROUND_HALF_UP` quantization.
- **Context:** Floating-point numbers use IEEE 754 binary representation, causing representation drift (e.g. `0.1 + 0.2 = 0.30000000000000004`).
- **Rationale:** Milk cooperative audits require that every intermediate and final payment balance matches to the exact paisa (Rs 0.01).
- **Consequences:** Every numeric constant is defined as a `Decimal("...")` string literal (e.g. `Decimal("0.50")`).

### ADR-05: Bilinear Two-Axis Rate Chart Interpolation (BR-02)
- **Decision:** Implement bilinear interpolation over nearest 0.1% Fat and 0.1% SNF grid points loaded from `rate_chart.csv` with formula fallback.
- **Mathematical Policy:**
  1. Determine lower coordinates: $F_1 = \lfloor(F - F_{base})/0.1\rfloor \times 0.1 + F_{base}$, $S_1 = \lfloor(S - S_{base})/0.1\rfloor \times 0.1 + S_{base}$.
  2. Bounding upper coordinates: $F_2 = F_1 + 0.1$, $S_2 = S_1 + 0.1$. If $F == F_1$, $F_2 = F_1$ to avoid out-of-grid indexing.
  3. Interpolate along SNF at $F_1$ and $F_2$, then interpolate along Fat between those results.
- **Rationale:** Guarantees exact pricing for fractional analyser outputs (e.g., Fat 4.20%, SNF 8.45% = Rs 36.05/L).

---

## 3. Business Policy & Financial Edge Case Decisions

### ADR-06: Precedence of Adulteration Suspension over Low-Fat Rejection (BR-01, BR-03)
- **Decision:** If a pouring has Fat < 3.00% AND `adulteration == true`, the adulteration rule takes strict precedence.
- **Rationale:** Low fat results only in a single-pouring rejection (`FAT_TOO_LOW`). Adulteration is an illegal practice that poisons bulk milk silos; it requires an immediate **7-day suspension** of the member (`ADULTERATION_POSITIVE`).
- **Implementation:** `pouring_service.py` checks `if pouring.adulteration:` before evaluating `if fat < Decimal("3.0"):`.

### ADR-07: Calendar Date Boundaries & Leap Year Resolution (BR-05)
- **Decision:** Cycle 3 always ends on the calendar last day of the month using `(date(year, month + 1, 1) - timedelta(days=1))`.
- **Rationale:** Correctly handles 28 or 29 days in February, 30 days in April/June/Sept/Nov, and 31 days in all other months without hardcoding date tables.
- **Payment Date Policy:** `payment_date = cycle_end + timedelta(days=3)`.

### ADR-08: Absolute Shift Count for Loyalty Bonus (BR-05)
- **Decision:** The loyalty bonus threshold is strictly **>= 15 distinct shifts** in every cycle, regardless of total cycle length.
- **Context:** In February cycle 21–28, there are only 8 days = 16 shifts.
- **Rationale:** The brief states: *"a member must pour on at least 15 of 20 shifts in a cycle"*. Planted scenario EC-05 confirms that the threshold is an absolute count of 15 shifts (M-003 with 15 shifts qualifies; M-011 with 14 shifts fails).

### ADR-09: Financial Safety Floor Cutback Order (BR-07)
- **Decision:** Recoveries must never reduce Net pay below **Rs 500.00** unless Gross itself is lower than Rs 500.00. Cutbacks are applied to **Loan recovery first, then Feed advance recovery**.
- **Context:** If Gross is Rs 1264.16, Feed is Rs 252.83, and 50% EMI is Rs 800.00, deducting full amounts would leave Net = Rs 211.33 (< Rs 500.00).
- **Policy:**
  1. If Gross < Rs 500.00, recoveries = Rs 0.00 (member receives raw Gross).
  2. If Net < Rs 500.00, shortage = `500.00 - Net`.
  3. `loan_cut = min(loan_recovery, shortage)`; `loan_recovery -= loan_cut`; shortage -= loan_cut.
  4. If shortage still > 0, `feed_recovery -= min(feed_recovery, shortage)`.
  5. Net is capped at exactly Rs 500.00.

### ADR-10: Member Exit Floor Exemption (BR-11)
- **Decision:** On `MEMBER_EXIT`, the partial cycle is closed immediately, and **all outstanding feed and loan balances are recovered in full, bypassing the Rs 500 floor**.
- **Rationale:** When a member exits the cooperative, the society cannot carry forward unpaid debt. The member's final net pay may fall below Rs 500.00 (e.g. EC Trap E for Member M-002, where Net pay is Rs 300.00).

### ADR-11: Sour Milk Loss Allocation (BR-09)
- **Decision:** Reversing pourings from rejected cans halves the monetary credit (`value × 0.50`), but **does not reduce physical accepted litres or shift counts**.
- **Rationale:** Souring happens during transport or chilling centre handling. The farmer delivered genuine milk at the collection centre, so attendance for loyalty and volume calculations remains intact, but the monetary loss is split 50% to the farmer and 50% to the village society settlement.

### ADR-12: Distinct Date Calculation for Society Commission Forfeit (BR-09)
- **Decision:** Commission forfeit requires can rejections on **$\ge$ 3 distinct calendar dates** (`rejected_ts.date()`).
- **Rationale:** Multiple can rejections arriving on the same day count as 1 return day (as verified in Trap C with Society S-1). A return arriving at `23:59:00` on the final cycle day counts as an independent distinct day (verified in EC-08 with Society S-2).

---

## 4. Summary Table of Architecture Decisions

| Decision ID | Area | Choice | Alternative Rejected |
|---|---|---|---|
| **ADR-01** | Stack | Pure Python 3.10+ Standard Library | Third-party packages (`pandas`, `tabulate`) |
| **ADR-02** | UI / Architecture | Batch command-stream CLI | Web app / REST API / SQLite database |
| **ADR-03** | Domain Model | Python `@dataclass` | Raw tuples / dictionaries |
| **ADR-04** | Arithmetic | `decimal.Decimal` with `ROUND_HALF_UP` | Python native `float` (IEEE 754 drift) |
| **ADR-05** | Pricing Engine | Bilinear 2D interpolation | Nearest-neighbor or formula-only lookup |
| **ADR-06** | Quality Policy | Adulteration suspension takes precedence | Pure low-fat rejection |
| **ADR-07** | Date Engine | Dynamic month-end subtraction | Hardcoded month day tables |
| **ADR-08** | Loyalty Rule | Strict absolute count of 15 shifts | Proportional percentage attendance |
| **ADR-09** | Floor Cutback | Cut Loan recovery first, then Feed | Pro-rata deduction cutback |
| **ADR-10** | Member Exit | Full balance clearance; floor bypassed | Enforcing Rs 500 floor on exit |
| **ADR-11** | Sour Loss | 50% value cut; litres/shifts unchanged | Litre deductions from shift totals |
| **ADR-12** | Forfeit Rule | Distinct `rejected_ts.date()` counting | Raw count of rejected cans |
