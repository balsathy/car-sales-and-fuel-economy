"""Download and normalize GoodCarBadCar monthly U.S. vehicle sales tables."""

from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from urllib.request import Request, urlopen


SALES_URLS = {
    2025: "https://www.goodcarbadcar.net/2025-u-s-auto-sales-figures-by-model-all-vehicle-ranked-2/",
    2026: "https://www.goodcarbadcar.net/2026-us-auto-sales-figures-by-model-all-vehicle-ranked/",
}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MAKES = (
    "Alfa Romeo", "Aston Martin", "Land Rover", "Mercedes-Benz", "Rolls-Royce",
    "Rivian", "Volkswagen", "Chevrolet", "Chrysler", "Mitsubishi", "Infiniti",
    "Maserati", "Polestar", "Porsche", "Genesis", "Hyundai", "Lamborghini",
    "McLaren", "Ferrari", "Cadillac", "Bentley", "Buick", "Dodge", "Fiat",
    "Ford", "GMC", "Honda", "Jeep", "Kia", "Lexus", "Lincoln", "Lucid",
    "Mazda", "Mini", "Nissan", "Ram", "Subaru", "Tesla", "Toyota", "Volvo",
    "Acura", "Audi", "BMW", "Bugatti", "Lotus", "Suzuki",
)


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table = []
            self.tables.append(self._table)
        elif tag == "tr" and self._table is not None:
            self._row = []
            self._table.append(self._row)
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join(" ".join(self._cell).split()))
            self._cell = None
        elif tag == "tr":
            self._row = None
        elif tag == "table":
            self._table = None


def _split_nameplate(value: str) -> tuple[str, str]:
    nameplate = re.sub(r"^\s*\d+\.?\s*", "", value).strip()
    for make in MAKES:
        if nameplate.casefold().startswith(make.casefold() + " "):
            return make, nameplate[len(make):].strip()
    parts = nameplate.split(maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"Unable to identify make and model in {value!r}")
    return parts[0], parts[1]


def parse_sales_html(html: str, year: int, source_url: str | None = None) -> dict:
    """Parse the source's monthly model table; unknown months are omitted, not zeroed."""
    parser = _TableParser()
    parser.feed(html)
    table = next(
        (rows for rows in parser.tables if any(
            len(row) >= 13 and row[0].strip().casefold() == "model"
            and all(month.casefold() in {cell.casefold() for cell in row[1:]} for month in MONTHS)
            for row in rows
        )),
        None,
    )
    if table is None:
        raise ValueError(f"No monthly sales table found for {year}")

    header_index = next(
        i for i, row in enumerate(table)
        if len(row) >= 13 and row[0].strip().casefold() == "model"
        and all(month.casefold() in {cell.casefold() for cell in row[1:]} for month in MONTHS)
    )
    header = [cell.strip().casefold() for cell in table[header_index]]
    month_indexes = {month: header.index(month.casefold()) for month in MONTHS}
    records: list[dict] = []
    for row in table[header_index + 1:]:
        if not row or not row[0].strip():
            continue
        try:
            make, model = _split_nameplate(row[0])
        except ValueError:
            continue
        for month_num, month in enumerate(MONTHS, 1):
            column = month_indexes[month]
            raw = row[column].strip() if column < len(row) else ""
            if not raw or raw in {"�", "-", "—", "N/A"}:
                continue
            try:
                units = int(raw.replace(",", "").replace("*", "").strip())
            except ValueError:
                continue
            records.append({
                "year": year,
                "month": month_num,
                "make": make,
                "model": model,
                "units": units,
                "source": "GoodCarBadCar",
                "source_url": source_url or SALES_URLS[year],
                "estimate_status": "not_specified_by_source",
            })

    available_months = sorted({record["month"] for record in records})
    if not records:
        raise ValueError(f"Monthly sales table for {year} contained no parseable records")
    return {
        "year": year,
        "source_url": source_url or SALES_URLS[year],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "available_months": available_months,
        "records": records,
        "coverage_note": (
            "Source table coverage may vary by model. Values are preserved as published; "
            "the source does not identify estimate status per row."
        ),
    }


def download_sales(year: int) -> dict:
    if year not in SALES_URLS:
        raise ValueError(f"Supported sales years: {', '.join(map(str, SALES_URLS))}")
    request = Request(SALES_URLS[year], headers={"User-Agent": "VehicleDataChatbot/1.0"})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")
    return parse_sales_html(html, year)
