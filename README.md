# T004-PS-098: Dairy Milk Payment Project

This is the capstone project for Team T004.

Team members: Akshatha B and Akshay H  
Language: Python 3.10+

## Project idea

The program will calculate milk prices and member payments for a dairy cooperative. It will read simple command and data files and create reports. There will be no user interface because the assignment asks for a command-file-driven program.

## Development plan

We will build the project in small stages so that each feature can be tested before the next one is added.

1. Project setup and common helpers
2. Basic records and input validation
3. Milk rate charts and price calculation
4. Pouring records and daily collection report
5. Member cycles, bonuses, and deductions
6. Disputes, adulteration, and member suspension
7. Sour-milk returns and society settlement
8. Full command runner, complete reports, and final testing

## Current progress

The basic project setup is ready. It contains the common money and date helpers and tests for them.

## How to run the tests

From this project folder, run:

```text
python -m unittest discover -s tests -v
```

The business rules will be added step by step. The final version will contain the full pricing, cycle payment, dispute, return, and settlement flow from `DESIGN.md`.
