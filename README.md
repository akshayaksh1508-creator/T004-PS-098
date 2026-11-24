# PS-098: Dairy Cooperative Milk Procurement Pricing & Payment Engine

**Team ID:** T004  
**Problem Statement:** PS-098  
**Domain:** Agri-Dairy / Batch Financial Processing Engine  
**Team Members:** Akshatha B (`1AT24CD008`) & Akshay H (`1AT24CD009`)  
**Language:** Python 3.10+ (Standard Library only — no external dependencies)  
Video link:https://drive.google.com/drive/folders/1vtddQ-vSsURWzuU6GPjGcjAdNOx26kzf?usp=sharing
---

## 1. Project Overview

This project implements the procurement engine used by a district milk union to:
- Receive milk twice daily (morning & evening shifts) across village collection societies.
- Test Fat % and Solid-Not-Fat (SNF) % and price each pouring using a two-axis bilinear rate chart.
- Apply quality adjustments (penalties for substandard SNF and temperature > 10°C; instant rejection and 7-day member suspension for adulteration).
- Accumulate pourings over 10-day payment cycles (`1–10`, `11–20`, `21–End of Month`).
- Apply seasonal bonuses (lean summer incentives) and volume penalties (flush winter quotas).
- Deduct cattle feed advances and loan EMIs while safeguarding small farmers via a **Rs 500.00 net payment floor**.
- Calculate village society commissions (2.5%), handling charges (Rs 0.20/L), transport subsidies (>15 km), and enforce 3-day sour-milk commission forfeit penalties.
- Handle member disputes with a 24-hour deadline and member exit final payouts.

The application is completely command-stream driven (no GUI) and outputs both formatted ASCII tables to the console and standard CSV files conforming to audit specifications.

---

## 2. Requirements & Setup

### Prerequisites
- **Python 3.10 or higher** installed on your system.
- No `pip install` required! The engine relies strictly on Python's built-in standard library (`decimal`, `datetime`, `csv`, `pathlib`, `dataclasses`, `unittest`).

### Verification of Python Version
```powershell
python --version
```
*(Ensure it outputs Python 3.10 or higher)*

---

## 3. How to Run the Application

Open PowerShell or Command Prompt, go to the project folder, and run:

```powershell

python main.py
```

That is all! You do not need to provide any folder path. `python main.py` automatically picks up the dataset, runs the complete engine, prints the tables in the terminal, and creates the CSV reports.

### Terminal & File Output
When executed, the engine:
1. Sequentially processes all commands (`PROCESS_SHIFT`, `DISPUTE`, `CAN_REJECT`, `MEMBER_EXIT`, `CLOSE_CYCLE`, `PRINT_*`).
2. Prints formatted ASCII report tables directly to the terminal:
   - **Collection Register**
   - **Member Cycle Statements**
   - **Society Settlements**
   - **Dispute Results**
3. Writes the 4 required CSV report files to the working directory:
   - `collection_register.csv`
   - `member_statements.csv`
   - `society_settlements.csv`
   - `dispute_results.csv`

---

## 4. Full Test Suite Execution

The repository contains an exhaustive test suite of **116 unit tests** covering every business rule (`BR-01` to `BR-11`), boundary conditions, edge cases, and planted traps.

### 1. Run the Complete Test Suite
```powershell
python -m unittest discover -s tests -v
```

Expected output:
```text
Ran 116 tests in 0.056s
OK
```

### 2. Run Individual Test Modules
You can also run specific test modules independently:

```powershell
# Test pricing, milk classification, and 2D bilinear interpolation (BR-01, BR-02)
python -m unittest tests/test_pricing.py -v

# Test pourings, quality deductions, adulteration, and 7-day suspension (BR-03, BR-04)
python -m unittest tests/test_pouring.py -v

# Test 10-day cycles, loyalty bonus, lean/flush seasonal rules, feed/loan recoveries, and Rs 500 floor (BR-05, BR-06, BR-07)
python -m unittest tests/test_cycles.py -v

# Test society commission, handling, transport subsidy, and 3-day return forfeit (BR-08, BR-09)
python -m unittest tests/test_society_settlement.py -v

# Test sour milk can rejections and 50% reversal (BR-09)
python -m unittest tests/test_can_returns.py -v

# Test 24-hr member disputes and re-testing (BR-10)
python -m unittest tests/test_disputes.py -v

# Test mid-cycle member exit and full balance recovery (BR-11)
python -m unittest tests/test_member_exit.py -v

# Test CSV report formatting, columns, and sorting
python -m unittest tests/test_reports.py -v
```

### 3. Run Planted Trap Verification
To verify the engine against all planted edge cases (EC-01 through EC-08) and trap scenarios in the sample data:

```powershell
python -m sample_data.verify_sample
```

Expected output:
```text
OK  PR-00385 chart_rate = 41.90 (expected 41.90) - EC-01 fat exactly 5.0 cow
OK  PR-00385 price_per_litre = 41.90 (expected 41.90) - EC-01
OK  PR-01375 chart_rate = 28.40 (expected 28.40) - EC-02 fat exactly 3.0
OK  PR-01449 chart_rate = 36.05 (expected 36.05) - EC-03 snf 8.45 interpolation
OK  PR-00177 value = 461.13 (expected 461.13) - 12.5 x 36.89 half-up
OK  PR-01063 temp_deduction = 0.00 (expected 0.00) - temp exactly 10
OK  PR-00668 status = REJECTED (expected REJECTED) - adulteration positive
OK  PR-00668 reject_reason = ADULTERATION_POSITIVE (expected ADULTERATION_POSITIVE) - trap
OK  PR-00740 reject_reason = MEMBER_SUSPENDED (expected MEMBER_SUSPENDED) - suspended
OK  PR-00856 reject_reason = MEMBER_SUSPENDED (expected MEMBER_SUSPENDED) - suspended
OK  PR-00867 status = ACCEPTED (expected ACCEPTED) - next day after suspension
M-004 suspended_until: 2026-01-31
OK  M-010 loyalty_bonus = 54.25 (expected 54.25) - EC-04 exactly 15 shifts
OK  M-003 Feb loyalty_bonus = 71.45 (expected 71.45) - EC-05 Feb 15 shifts qualifies
OK  M-011 Feb loyalty_bonus = 0.00 (expected 0.00) - EC-05 Feb 14 shifts does not qualify
OK  M-001 loan_recovery = 3400.00 (expected 3400.00) - EC-06 exact 2x EMI recovery
OK  RT-007 value_used = 4.40 (expected 4.40) - EC-07 retest lower than original
OK  S-2 commission_forfeited = True (expected True) - EC-08 3rd return at 23:59
```

---

## 5. Project Directory Structure

```text
T004-PS-098/
├── README.md               # User manual and test guide (this document)
├── DECISION_LOG.md         # Architectural & policy decision log (ADRs)
├── DESIGN.md               # System design specification
├── GUIDE.md                # Exhaustive viva study guide and live coding handbook
├── main.py                 # CLI dispatcher reading commands.txt
├── models.py               # Domain dataclasses
├── file_reader.py          # CSV loading utilities
├── validators.py           # Domain validation rules
├── pricing.py              # Bilinear interpolation & rate chart lookup
├── pouring_service.py      # Pouring reception, quality penalties, suspensions
├── cycle_service.py        # 10-day cycle closing, loyalty, recoveries, Rs 500 floor
├── society_service.py      # Society commission, handling, subsidies, forfeit
├── dispute_service.py      # 24-hr dispute validation and re-pricing
├── can_return_service.py   # Chilling centre can rejection and 50% reversal
├── member_exit_service.py  # Mid-cycle member exit and full loan/feed clearance
├── reports.py              # CSV persistence and terminal ASCII table generator
└── tests/                  # Full 116-test suite covering all rules and edge cases
    ├── test_can_returns.py
    ├── test_cycles.py
    ├── test_disputes.py
    ├── test_member_exit.py
    ├── test_part1.py
    ├── test_pouring.py
    ├── test_pricing.py
    ├── test_reports.py
    └── test_society_settlement.py
```

---

## 6. Business Rules Quick Reference

- **BR-01 (Milk Types):** Fat < 3.0% rejected (`FAT_TOO_LOW`); 3.0%–5.0% = Cow; > 5.0% = Buffalo; Mixed = Cow chart.
- **BR-02 (Rate Chart & Interpolation):** Bilinear 2D interpolation over 0.1% Fat and SNF steps.
- **BR-03 (Quality & Suspensions):** Substandard SNF deducts Rs 1.00/L; temperature > 10°C deducts Rs 0.50/L; adulteration positive rejects pouring and triggers a 7-day suspension.
- **BR-04 (Rounding):** Prices and pouring values rounded half-up to paisa (0.01). Litres recorded to 0.1 L.
- **BR-05 (10-Day Cycles & Loyalty Bonus):** Cycles `1–10`, `11–20`, `21–End of Month`. Payout on `cycle_end + 3 days`. Loyalty bonus = Rs 0.50/L on all litres for pouring on `>= 15` distinct shifts.
- **BR-06 (Seasonal Incentives):** Lean bonus (April–July) = +Rs 1.00/L. Flush penalty (October–January) = Rs 0.25/L on daily volume exceeding 150% of the previous cycle's daily average.
- **BR-07 (Recoveries & Rs 500 Floor):** Feed recovery = `min(balance, 20% of Gross)`. Full EMI if `Gross - Feed >= 2 × Due`, else 50% carried. Net pay never drops below Rs 500.00 (cuts loan first, then feed).
- **BR-08 (Society Commission):** 2.5% commission + Rs 0.20/L handling + Rs 0.15/L transport subsidy (>15 km).
- **BR-09 (Sour Milk Returns):** 50% value reversed (50% member, 50% society). Can rejections on `>= 3` distinct days forfeits society commission and handling.
- **BR-10 (Disputes):** Appeals allowed within `<= 24 hours`; uses `max(original, retest)`.
- **BR-11 (Member Exit):** Payout on exit date; full feed and loan balance clearance bypassing the Rs 500 floor.

For in-depth explanations and design trade-offs, consult [DECISION_LOG.md](DECISION_LOG.md) and [GUIDE.md](GUIDE.md).
