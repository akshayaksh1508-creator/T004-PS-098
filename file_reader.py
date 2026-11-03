import csv


def read_csv_file(file_name):
    with open(file_name, "r", newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))
