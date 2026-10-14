"""
main.py – Entry point for the Dairy Cooperative Milk Procurement Engine
Usage:
    python main.py <command_file.jsonl> [output_file]

If output_file is omitted, output is printed to stdout.
Team T004 · PS-098
"""
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)

# Allow running from project root without installing as package
sys.path.insert(0, str(Path(__file__).parent))

from commands import run_command_file


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <command_file.jsonl> [output_file]")
        sys.exit(1)

    command_file = sys.argv[1]
    if len(sys.argv) >= 3:
        out_path = Path(sys.argv[2])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as out_fh:
            run_command_file(command_file, out_fh)
        print(f"Output written to: {out_path}")
    else:
        run_command_file(command_file)


if __name__ == "__main__":
    main()
