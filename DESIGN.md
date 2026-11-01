# T004-PS-098: Dairy Milk Payment Project

**Team:** T004  
**Members:** Akshatha B and Akshay H  
**Language:** Python 3.10+

## 1. What we are building

We are building a small command-line program for a dairy cooperative. The program will read milk collection details from CSV files and calculate how much each member should be paid.

There is no website or mobile app in this project. We will use input files and generate output files. This matches the assignment requirement and keeps the project easy to understand.

We will write the code in a simple way because both of us should be able to explain and change it during the viva:

- small functions with clear names;
- simple classes and dictionaries where they make the data easier to understand;
- `Decimal` for money instead of floating-point arithmetic;
- CSV files for input and output;
- no database or web framework in the first version;
- no complicated design patterns unless they are really needed.

## 2. What our project will do

### Main features

1. Register unions, societies, members, rate charts, feed advances, and loan schedules.
2. Validate and record AM/PM milk pourings.
3. Calculate cow, buffalo, and declared mixed-milk prices.
4. Apply two-axis interpolation and quality adjustments.
5. Reject invalid or adulterated pourings and suspend members when required.
6. Record disputes and use the higher re-test reading.
7. Close 10-day cycles and calculate bonuses, deductions, and recoveries.
8. Calculate society commission and transport subsidy.
9. Process sour-milk can returns and disputes.
10. Print daily registers, member statements, payment advice, and society settlements.

### We are not adding these now

- graphical screens;
- online payments;
- automatic milk-analyser calibration;
- cattle-insurance deductions;
- a database server.

## 3. Simple program flow

```text
Input CSV files
      |
      v
Command runner  --->  Validation functions
      |                         |
      v                         v
In-memory records  --->  Pricing engine  --->  Pouring prices
      |                         |
      v                         v
Cycle engine       --->  Member statements
      |
      v
Society settlement engine  --->  Reports and payment advice
```

The program will work in this order:

1. Read the CSV files.
2. Check whether the data is valid.
3. Calculate the price for every pouring.
4. Group the accepted pourings into 10-day cycles.
5. Calculate bonuses, deductions, and final payment.
6. Create the required reports.

The calculation functions will receive data as arguments instead of reading files themselves. This makes them easier to test and change.

## 4. Data we need to store

| Record | Important fields |
|---|---|
| `Union` | `union_id`, `name`, `chilling_centre_id` |
| `Society` | `society_id`, `union_id`, `name`, `commission_rate`, `distance_km` |
| `Member` | `member_id`, `society_id`, `name`, `cattle_type`, `feed_balance`, `loan_balance`, `emi`, `status`, `suspended_until` |
| `RateChart` | `milk_type`, `base_fat`, `base_snf`, `base_price`, `fat_step_price`, `snf_step_price` |
| `Pouring` | `pouring_id`, `member_id`, `society_id`, `date`, `shift`, `litres`, `fat`, `snf`, `temperature`, `adulteration`, `can_id` |
| `PricedPouring` | pouring details plus `accepted`, `rejection_reason`, `price_per_litre`, `value`, `quality_adjustment` |
| `Dispute` | `dispute_id`, `pouring_id`, `raised_at`, `new_fat`, `new_snf`, `status` |
| `CanReturn` | `return_id`, `society_id`, `can_id`, `return_date`, `reason` |

For money, we will use Python's `Decimal` so that the result is correct to the paisa. Litres will be stored to one decimal place.

## 5. Input and output files

### Input files

- `unions.csv`
- `societies.csv`
- `members.csv`
- `rate_charts.csv`
- `pourings.csv`
- `disputes.csv`
- `can_returns.csv`
- `commands.csv`

Every file will have a header row. We will keep IDs as text so that leading zeroes are not lost. Dates will use `YYYY-MM-DD` and timestamps will use `YYYY-MM-DD HH:MM`.

### Output files

- `pouring_prices.csv` - one row per pouring, including accepted/rejected reason.
- `daily_collection_register.csv` - daily totals by society and milk type.
- `member_cycle_statements.csv` - gross, bonuses, deductions, recoveries, and net payment.
- `payment_advice.txt` - readable member-wise payment advice.
- `society_settlements.csv` - gross value, commission, handling, subsidy, returns, and final settlement.
- `errors.csv` - rejected input rows with a stable error code and message.

## 6. Business rules from the assignment

Rules are numbered so the team can refer to them in tests, design review, and viva answers.

### BR-01: Milk type

Fat below `3.0%` is rejected. Fat from `3.0%` to `5.0%` uses the cow chart, and fat above `5.0%` uses the buffalo chart. Fat exactly `5.0%` is cow milk. Mixed milk is declared by the member and uses the cow chart.

### BR-02: Rate chart and interpolation

The rate chart has fat steps of `0.1` and SNF steps of `0.1`. Readings between steps are linearly interpolated on both axes. The cow base is `Rs 32.00` at fat `3.5`, SNF `8.5`; every `0.1` fat adds `Rs 0.60`, and every `0.1` SNF adds `Rs 0.30`. The buffalo base is `Rs 48.00` at fat `6.0`, SNF `9.0`; every `0.1` fat adds `Rs 0.70`, and every `0.1` SNF adds `Rs 0.20`.

### BR-03: Quality adjustments and adulteration

SNF below `8.0` for cow/mixed milk deducts `Rs 1.00` per litre. SNF below `8.5` for buffalo milk deducts `Rs 1.00` per litre. Temperature above `10°C` deducts `Rs 0.50` per litre. Adulteration-positive milk is rejected and the member is suspended for seven days.

### BR-04: Rounding

Price per litre is rounded to the paisa. Pouring value is calculated as litres multiplied by the rounded price and is then rounded to the paisa. Litres are measured to `0.1`.

### BR-05: Payment cycle and loyalty bonus

Cycles are days `1-10`, `11-20`, and `21-end of month`. Payment is made on the third day after the cycle closes. A member must pour on at least 15 of 20 shifts to receive a loyalty bonus of `Rs 0.50` per litre on all litres in that cycle. The February `21-28` case will be handled using the actual available dates.

### BR-06: Seasonal bonus and penalty

During April to July, accepted milk receives a bonus of `Rs 1.00` per litre. During October to January, a penalty of `Rs 0.25` per litre applies to litres above 150% of the member's previous-cycle average daily litres.

### BR-07: Feed and loan deductions

Feed advances are recovered at 20% of cycle gross payment until cleared. Loan EMI is recovered in full if gross after feed recovery is at least two times the EMI. Otherwise, 50% of the EMI is recovered and the balance is carried forward. Recoveries must not reduce net payment below `Rs 500`, unless gross payment itself is lower.

### BR-08: Society commission and transport subsidy

Society commission is 2.5% of members' gross pouring value plus `Rs 0.20` per litre handling. Transport subsidy is `Rs 0.15` per litre when the society is more than 15 km from the chilling centre.

### BR-09: Sour-milk return

When the chilling centre rejects a society can, the can is identified by its can ID and all pourings in that can are reversed at 50% of value. The member bears half of the value adjustment. If a society has returns on three or more days in a cycle, it loses its commission for that cycle. A return at 23:59 on the third distinct day counts as the third day.

### BR-10: Dispute and re-test

A member may dispute a fat or SNF reading within 24 hours. The re-test is recorded and the higher of the original and re-test readings is used. A lower re-test does not reduce the original reading. A dispute after 24 hours is rejected.

### BR-11: Member exit

When a member exits, the final cycle is paid immediately. All outstanding feed and loan balances are recovered in full, even if this makes the payment lower than `Rs 500`.

### Supporting input validation

The program will also validate IDs, dates, shifts, litres, member/society references, and duplicate records so that the 11 business rules can be applied to clean data. These are program checks, not additional business rules from the assignment.

## 7. How we will calculate a pouring price

For each pouring, the program will do the following:

1. Validate member, society, date, shift, litres, and suspension status.
2. Apply adulteration and fat rejection rules.
3. Select the chart: cow, buffalo, or cow for declared mixed milk.
4. Find the surrounding fat and SNF steps.
5. Calculate the base price at the four surrounding points, then interpolate fat and SNF.
6. Apply SNF and temperature adjustments per litre.
7. Round the final price per litre to two decimal places.
8. Calculate and round the pouring value.
9. Store the result with an acceptance flag and rule code.

We will write interpolation as small steps instead of using one complicated formula. This will be easier to explain in the viva:

```text
fat_price_low  = price at lower fat and requested SNF
fat_price_high = price at higher fat and requested SNF
base_price = interpolate between fat_price_low and fat_price_high
```

The assignment gives fixed increments, but we will still keep an `interpolate()` function. If the rate chart changes later, we can update the chart without rewriting the whole pricing program.

## 8. How we will close a 10-day cycle

For every member and cycle, we will:

1. Select accepted pourings within the cycle.
2. Sum pouring values to get gross pouring value.
3. Count distinct accepted pouring shifts.
4. Add loyalty and seasonal bonuses when their rules are satisfied.
5. Apply sour-milk return adjustments.
6. Recover feed advance and loan EMI using the recovery floor.
7. If the member is exiting, recover all outstanding balances and skip the floor.
8. Save a statement with every intermediate amount and rule code.
9. Calculate the payment date and write payment advice.

The statement will show each amount separately. For example, gross amount, loyalty bonus, feed recovery, loan recovery, and final amount will all be visible. This will help us find mistakes.

## 9. How we will calculate society settlement

For each society and cycle:

1. Sum gross accepted pouring values.
2. Sum accepted litres.
3. Calculate commission and handling charge.
4. Add transport subsidy when distance is greater than 15 km.
5. Apply can-return adjustments.
6. Count distinct return dates.
7. Set commission to zero when return days are three or more.
8. Write the final settlement with all components.

## 10. Invalid data handling

If one row is wrong, we will save the error in `errors.csv` and continue with other valid rows where possible. The error file will contain:

```text
row_number,record_type,record_id,error_code,error_message
```

Examples of stable error codes are `UNKNOWN_MEMBER`, `INVALID_SHIFT`, `FAT_TOO_LOW`, `ADULTERATION_REJECTED`, `DISPUTE_TOO_LATE`, and `DUPLICATE_POURING`.

## 11. Testing plan

We will write small tests for the important business rules and at least one complete cycle test. Each test name will explain what it is checking.

Important mandatory cases:

- fat exactly `3.0` is accepted;
- fat exactly `5.0` uses the cow chart;
- fat below `3.0` is rejected;
- SNF `8.45` interpolates correctly;
- exactly 15 shifts receives loyalty bonus;
- February cycle `21-28` handles only available dates;
- gross after feed recovery exactly equals two times EMI and receives full EMI recovery;
- lower re-test leaves original reading unchanged;
- a can return at `23:59` on the third distinct day removes commission;
- member exit recovers all balances even when net would be below `Rs 500`;
- temperature and SNF deductions are applied independently;
- repeated files do not create duplicate members or pourings.

## 12. Decisions we will confirm when sample files arrive

The brief does not give the exact command syntax or CSV column names. Until the sample files arrive, we will use simple column names and document any changes in `README.md`.

The brief also does not state the maximum chart range. The first implementation will reject a test reading outside the configured chart range with `RATE_OUT_OF_RANGE` rather than silently extrapolating. This can be changed easily if the supplied Week 2 files define an extrapolation rule.

## 13. Our implementation order

1. Create the project structure and README.
2. Implement money/date/CSV helpers.
3. Implement records and validation.
4. Implement rate lookup and pricing tests.
5. Implement cycle and recovery calculations.
6. Implement disputes and can returns.
7. Implement society settlements and reports.
8. Add integration tests using sample data.
9. Run a final beginner-readability review and prepare the PDF design document.

