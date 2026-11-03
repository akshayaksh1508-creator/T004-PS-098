# T004-PS-098: Dairy Milk Payment Project

This is the capstone project for Team T004.

Team members: Akshatha B and Akshay H  
Language: Python 3.10+

## Project idea

The program will calculate milk prices and member payments for a dairy cooperative. It will read simple command and data files and create reports. There will be no user interface because the assignment asks for a command-file-driven program.

## Development plan

We are developing the project in eight parts. Each part will be committed separately so that the work can be followed in Git history.

1. Project setup and common helpers
2. Basic records and input validation
3. Milk rate charts and price calculation
4. Pouring records and daily collection report
5. Member cycles, bonuses, and deductions
6. Disputes, adulteration, and member suspension
7. Sour-milk returns and society settlement
8. Full command runner, complete reports, and final testing

## Part 1 completed in this commit

- created a small `app` Python package;
- added common money rounding using `Decimal`;
- added cycle date helper functions;
- added tests for these common helpers;
- added a `.gitignore` for Python files and generated reports.

## How to run the tests

From this project folder, run:

```text
python -m unittest discover -s tests -v
```

The business rules will be added step by step. The final version will contain the full pricing, cycle payment, dispute, return, and settlement flow from `DESIGN.md`.
