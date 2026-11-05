"""Download and normalize EPA FuelEconomy.gov vehicle data."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO
from urllib.request import Request, urlopen


EPA_CSV_URL = "https://www.fueleconomy.gov/feg/epadata/vehicles.csv"
SUPPORTED_YEARS = (2025, 2026)


def parse_epa_csv(csv_text: str, years: tuple[int, ...] = SUPPORTED_YEARS) -> dict:
    reader = csv.DictReader(StringIO(csv_text))
    required = {"id", "year", "make", "model", "comb08"}
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise ValueError("EPA vehicle CSV is missing required columns")

    rows = []
    for row in reader:
        try:
            model_year = int(row["year"])
        except (ValueError, TypeError):
            continue
        if model_year not in years:
            continue
        try:
            combined = float(row["comb08"])
        except (ValueError, TypeError):
            combined = 0
        if not row.get("make") or not row.get("model") or combined <= 0:
            continue
        rows.append({
            "id": row["id"],
            "year": model_year,
            "make": row["make"].strip(),
            "model": row["model"].strip(),
            "base_model": (row.get("baseModel") or row["model"]).strip(),
            "fuel_type": (row.get("fuelType") or row.get("fuelType1") or "").strip(),
            "fuel_type_1": (row.get("fuelType1") or "").strip(),
            "vehicle_type": (row.get("atvType") or "").strip(),
            "city_mpg": _number(row.get("city08")),
            "highway_mpg": _number(row.get("highway08")),
            "combined_mpg_or_mpge": combined,
            "combined_miles_per_kg": _number(row.get("combMpk")),
            "source": "U.S. EPA FuelEconomy.gov",
            "source_url": EPA_CSV_URL,
        })
    if not rows:
        raise ValueError(f"No EPA vehicle records found for model years {years}")
    return {
        "source_url": EPA_CSV_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "model_years": list(years),
        "records": rows,
        "coverage_note": (
            "Ratings are for EPA model years and configurations; they are not sales-weighted. "
            "Electric-vehicle combined ratings are MPGe, not gasoline MPG."
        ),
    }


def _number(value: str | None) -> float | None:
    try:
        number = float(value or "")
    except ValueError:
        return None
    return number if number > 0 else None


def download_epa(years: tuple[int, ...] = SUPPORTED_YEARS) -> dict:
    request = Request(EPA_CSV_URL, headers={"User-Agent": "VehicleDataChatbot/1.0"})
    with urlopen(request, timeout=60) as response:
        csv_text = response.read().decode("utf-8-sig", errors="replace")
    return parse_epa_csv(csv_text, years)
