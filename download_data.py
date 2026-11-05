"""Command-line downloads used by the batch launcher."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from downloaders.epa import download_epa
from downloaders.sales import download_sales


DATA_DIR = Path(__file__).resolve().parent / "data"
SALES_FILE = DATA_DIR / "sales.json"
EPA_FILE = DATA_DIR / "mileage.json"


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def _save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _merge_sales(existing: dict, incoming: dict) -> dict:
    records = [r for r in existing.get("records", []) if r["year"] != incoming["year"]]
    records.extend(incoming["records"])
    return {**incoming, "records": records}


def main() -> int:
    parser = argparse.ArgumentParser(description="Download vehicle sales or EPA mileage data.")
    commands = parser.add_subparsers(dest="source", required=True)
    sales = commands.add_parser("sales", help="Download monthly sales for one year.")
    sales.add_argument("year", type=int, choices=(2025, 2026))
    commands.add_parser("epa", help="Download EPA mileage for 2025 and 2026.")
    args = parser.parse_args()

    try:
        DATA_DIR.mkdir(exist_ok=True)
        if args.source == "sales":
            incoming = download_sales(args.year)
            _save(SALES_FILE, _merge_sales(_load(SALES_FILE), incoming))
            print(f"Downloaded {len(incoming['records'])} sales records for {args.year}.")
        else:
            incoming = download_epa()
            _save(EPA_FILE, incoming)
            print(f"Downloaded {len(incoming['records'])} EPA vehicle configurations.")
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
