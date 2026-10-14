<<<<<<< HEAD
# T004-PS-098 · Dairy Cooperative Milk Procurement Pricing and Member Payment Engine

**Team T004** | Akshatha B (1AT24CD008) · Akshay H (1AT24CD009) | Section CSDS A

---

## Problem Statement
PS-098 — Build the procurement engine a district milk union uses to receive milk twice daily, test fat and SNF, price each pouring on a two-axis rate chart with quality adjustments and rejections, accumulate member payments over 10-day cycles with loyalty and seasonal bonuses, deduct feed and loan recoveries, and pay the collection society its commission.

---

## How to Run

### Prerequisites
```bash
pip install pytest
```

### Run the engine on a command file
```bash
python src/main.py data/sample/sample_commands.jsonl
```

### Run with output to a file
```bash
python src/main.py data/sample/sample_commands.jsonl output/my_output.txt
```

### Run all tests (single command)
```bash
pytest tests/ -v
```

---

## Project Structure

```
T004-PS-098/
├── src/
│   ├── main.py          # CLI entry point
│   ├── models.py        # Domain entities (Union, Society, Member, Pouring, …)
│   ├── engine.py        # All business rules BR-01 → BR-27
│   ├── store.py         # In-memory data registry with indexing helpers
│   ├── commands.py      # JSONL command-file parser and dispatcher
│   └── reports.py       # Formatted report generators
├── tests/
│   └── test_engine.py   # 68 pytest tests covering every business rule + edge cases
├── data/
│   └── sample/
│       └── sample_commands.jsonl   # Complete demo command file
├── output/              # Engine outputs go here
├── docs/                # Design document (PDF added at Week 4)
└── README.md
```

---

## Command File Format (JSONL)

Each line is a JSON object with a `"command"` key. Lines starting with `#` are treated as comments.

### Supported Commands

| Command | Description |
|---------|-------------|
| `REGISTER_UNION` | Register a milk union |
| `REGISTER_SOCIETY` | Register a collection society |
| `REGISTER_MEMBER` | Register a farmer member (with optional loans/feed advances) |
| `REGISTER_RATE_CHART` | Load fat/SNF rate chart |
| `RECORD_POURING` | Record a milk pouring (validated + priced immediately) |
| `FILE_DISPUTE` | File a fat/SNF reading dispute |
| `RESOLVE_DISPUTE` | Record re-test result |
| `RECORD_SOUR_RETURN` | Record chilling-centre can rejection |
| `CLOSE_CYCLE` | Close a 10-day payment cycle (prints all statements) |
| `EXIT_MEMBER` | Process member exit (immediate full settlement) |
| `PRINT_DAILY_REGISTER` | Print daily collection register for a society |
| `PRINT_MEMBER_STATEMENT` | Print a member's cycle payment advice |
| `PRINT_SOCIETY_SETTLEMENT` | Print society settlement sheet |

### Example Commands

```jsonl
{"command": "register_union", "union_id": "U001", "name": "Mandya District Milk Union", "chilling_centre_id": "CC001"}
{"command": "register_rate_chart", "chart_id": "COW-2024", "milk_type": "COW", "base_fat": "3.5", "base_snf": "8.5", "base_price": "32.00", "fat_increment": "0.60", "snf_increment": "0.30", "effective_from": "2024-01-01"}
{"command": "record_pouring", "pouring_id": "P001", "member_id": "M001", "society_id": "SOC001", "pouring_datetime": "2024-10-01T06:00:00", "shift": "AM", "litres": "12.0", "fat": "4.0", "snf": "8.5", "temperature_c": "8.0", "adulteration_flag": false, "can_id": "CAN001", "milk_type": "COW"}
{"command": "close_cycle", "society_id": "ALL", "cycle_start": "2024-10-01", "cycle_end": "2024-10-10"}
```

---

## Business Rules Implemented

| ID | Rule |
|----|------|
| BR-01 | Fat < 3.0% → REJECTED |
| BR-02 | Fat 3.0–5.0% → COW; fat > 5.0% → BUFFALO |
| BR-03 | MIXED declared by member → priced on COW chart |
| BR-04 | Rate chart: fat steps 0.1, SNF steps 0.1 |
| BR-05 | Linear interpolation on both axes |
| BR-06 | SNF < 8.0 (cow) or < 8.5 (buffalo) → Rs 1.00/litre deduction |
| BR-07 | Temperature > 10°C → Rs 0.50/litre deduction |
| BR-08 | Adulteration → REJECT pouring + 7-day member suspension |
| BR-09 | Prices rounded to paisa; pouring value = litres × price (rounded) |
| BR-10 | Cycles: 1–10, 11–20, 21–end-of-month |
| BR-11 | ≥ 15 shifts in cycle → loyalty bonus Rs 0.50/litre |
| BR-12 | Lean months (Apr–Jul) → flat Rs 1.00/litre bonus |
| BR-13 | Flush months (Oct–Jan) → Rs 0.25/litre penalty on litres > 150% prev avg |
| BR-14 | Feed advance recovery: 20% of cycle gross |
| BR-15 | Loan EMI: full if after-feed ≥ 2× EMI; else 50% |
| BR-16 | Net payment floor: Rs 500 (unless gross itself < 500) |
| BR-17–21 | Payment date: 3rd day after cycle close; member exit: immediate full recovery |
| BR-22 | Society commission: 2.5% of gross + Rs 0.20/litre handling |
| BR-23 | Transport subsidy: Rs 0.15/litre if distance > 15 km |
| BR-24 | Sour-milk return: all pourings in can reversed at 50% value |
| BR-25 | ≥ 3 sour-return days in cycle → society loses commission |
| BR-26 | Dispute must be filed within 24 hours of pouring |
| BR-27 | Re-test: higher of original/retest used; if lower → original stands |

---

## Edge Cases Explicitly Tested

- Fat exactly 5.0% → COW chart (not BUFFALO)
- Fat exactly 3.0% → accepted at lowest cow rate
- SNF 8.45 → interpolated between 8.4 and 8.5
- Member pouring on exactly 15 shifts → loyalty bonus qualifies
- Feb cycle C3 (21–28) → 16 shifts available
- Loan EMI recovery when gross after feed is exactly 2× EMI
- Re-test lower than original → original stands
- Can rejected on 3rd distinct day at 23:59 → commission forfeited

---

## Design Decisions (Decision Log)

See `docs/decision_log.md` for full log. Key decisions:

1. Used `Decimal` throughout for exact paisa-level arithmetic (no float rounding errors)
2. JSONL command-file format allows easy batch processing and reproducible runs
3. In-memory `DataStore` with multiple indexes (by member, society, can) for O(1) lookups
4. `MilkType.MIXED` maps to COW chart at price-lookup time (BR-03)
5. Recovery floor restored in priority order: loan first, then feed (preserves more fee recovery)
6. Society `sour_return_days` is a `set[date]` — deduplicates multiple cans on same day correctly
7. Suspension check is lazy (checked at pour time, lifted automatically when date passes)
8. `get_cycle_bounds()` uses `calendar.monthrange` to correctly handle February leap years
=======
# T004-PS-098
>>>>>>> d54ddafa1f084c2859e6400be72aa8e9e31ace38
