"""Deterministic answers for common sales and EPA fuel-economy questions."""

from __future__ import annotations

import calendar
import re


MILEAGE_WORDS = {"mileage", "milage", "mpg", "mpge", "fuel economy"}
QUESTION_WORDS = {
    "a", "an", "and", "are", "best", "car", "cars", "do", "does", "economy",
    "for", "fuel", "get", "has", "have", "highest", "how", "is", "most",
    "of", "please", "tell", "the", "what", "which", "with",
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _edit_distance(first: str, second: str) -> int:
    distances = [[0] * (len(second) + 1) for _ in range(len(first) + 1)]
    for i in range(len(first) + 1):
        distances[i][0] = i
    for j in range(len(second) + 1):
        distances[0][j] = j
    for i in range(1, len(first) + 1):
        for j in range(1, len(second) + 1):
            cost = 0 if first[i - 1] == second[j - 1] else 1
            distances[i][j] = min(
                distances[i - 1][j] + 1,
                distances[i][j - 1] + 1,
                distances[i - 1][j - 1] + cost,
            )
            if (
                i > 1 and j > 1
                and first[i - 1] == second[j - 2]
                and first[i - 2] == second[j - 1]
            ):
                distances[i][j] = min(distances[i][j], distances[i - 2][j - 2] + 1)
    return distances[-1][-1]


def _has_mileage_intent(message: str) -> bool:
    text = _norm(message)
    if re.search(r"\b(?:mpg|mpge)\b", text) or "fuel economy" in text:
        return True
    return any(
        _edit_distance(word, "mileage") <= 1
        for word in text.split()
        if len(word) >= 5
    )


def _has_sales_intent(message: str) -> bool:
    text = _norm(message)
    return bool(re.search(r"\b(?:sold|sales|sell|selling|units)\b", text))


def _requested_nameplate(message: str, sales_records: list[dict]) -> str | None:
    question = _norm(message)
    nameplates = sorted({
        f'{record["make"]} {record["model"]}'
        for record in sales_records
        if record.get("make") and record.get("model")
    }, key=lambda value: len(_norm(value)), reverse=True)

    for nameplate in nameplates:
        normalized = _norm(nameplate)
        if re.search(rf"\b{re.escape(normalized)}s?\b", question):
            return nameplate

    question_tokens = [
        token for token in question.split()
        if token not in QUESTION_WORDS
    ]
    fuzzy_matches: list[tuple[int, str]] = []
    for nameplate in nameplates:
        make, model = nameplate.split(" ", 1)
        make_tokens = _norm(make).split()
        model_tokens = _norm(model).split()
        if not model_tokens or not all(token in question_tokens for token in make_tokens):
            continue
        remaining_tokens = [token for token in question_tokens if token not in make_tokens]
        best_distance: int | None = None
        for start in range(len(remaining_tokens) - len(model_tokens) + 1):
            window = remaining_tokens[start:start + len(model_tokens)]
            distances = []
            for actual, expected in zip(window, model_tokens):
                if actual == expected:
                    distances.append(0)
                elif len(actual) >= 5 and len(expected) >= 5 and _edit_distance(actual, expected) <= 2:
                    distances.append(_edit_distance(actual, expected))
                else:
                    break
            else:
                distance = sum(distances)
                best_distance = distance if best_distance is None else min(best_distance, distance)
        if best_distance is not None:
            fuzzy_matches.append((best_distance, nameplate))

    if not fuzzy_matches:
        return None
    minimum = min(distance for distance, _ in fuzzy_matches)
    closest = {nameplate for distance, nameplate in fuzzy_matches if distance == minimum}
    return next(iter(closest)) if len(closest) == 1 else None


def _sales_totals(sales: dict, year: int) -> dict[str, int]:
    totals: dict[str, int] = {}
    for record in sales.get("records", []):
        if record["year"] == year:
            nameplate = f'{record["make"]} {record["model"]}'
            totals[nameplate] = totals.get(nameplate, 0) + record["units"]
    return totals


def _year_from_question(message: str, default: int) -> int:
    match = re.search(r"\b(2025|2026)\b", message)
    return int(match.group(1)) if match else default


def _matching_sales_nameplate(message: str, totals: dict[str, int]) -> str | None:
    question = _norm(message)
    candidates = sorted(totals, key=lambda name: len(_norm(name)), reverse=True)
    for name in candidates:
        normalized = _norm(name)
        if normalized and re.search(rf"\b{re.escape(normalized)}s?\b", question):
            return name
    return None


def _sales_model_index(sales_records: list[dict]) -> dict[str, list[tuple[str, str]]]:
    index: dict[str, list[tuple[str, str]]] = {}
    seen = set()
    for record in sales_records:
        make = _norm(record["make"])
        model = _norm(record["model"])
        nameplate = f'{record["make"]} {record["model"]}'
        key = (make, model, nameplate)
        if key not in seen:
            index.setdefault(make, []).append((model, nameplate))
            seen.add(key)
    return index


def _matched_sales_names(
    mileage_record: dict,
    sales_index: dict[str, list[tuple[str, str]]],
) -> set[str]:
    make = _norm(mileage_record.get("make", ""))
    models = {
        _norm(mileage_record.get("base_model", "")),
        _norm(mileage_record.get("model", "")),
    }
    matched = set()
    for sales_model, nameplate in sales_index.get(make, []):
        if sales_model in models:
            matched.add(nameplate)
            continue
        if (make, sales_model) == ("ford", "f series") and any(
            re.fullmatch(r"f ?\d{3}", model) for model in models
        ):
            matched.add(nameplate)
        elif (make, sales_model) == ("ram", "pickup") and any(
            re.fullmatch(r"(ram )?(1500|2500|3500)", model) for model in models
        ):
            matched.add(nameplate)
        elif (make, sales_model) in {
            ("chevrolet", "silverado"), ("gmc", "sierra")
        } and any(
            model.startswith(sales_model + " ") for model in models
        ):
            matched.add(nameplate)
    return matched


def _is_electric(record: dict) -> bool:
    kind = _norm(record.get("vehicle_type", ""))
    fuel = _norm(record.get("fuel_type", ""))
    return kind == "ev" or fuel == "electricity"


def _is_hydrogen(record: dict) -> bool:
    fuel = _norm(record.get("fuel_type_1") or record.get("fuel_type", ""))
    return "hydrogen" in fuel or _norm(record.get("vehicle_type", "")) == "fcv"


def answer(message: str, sales: dict | None = None, mileage: dict | None = None) -> str:
    sales = sales or {}
    mileage = mileage or {}
    text = message.strip()
    lowered = text.casefold()
    if not text:
        return "Ask me about 2025 or 2026 model sales, or EPA fuel economy for a model year."

    if _has_mileage_intent(text):
        records = mileage.get("records", [])
        if not records:
            return "No EPA mileage data is loaded yet. Use “Download EPA mileage” first."
        year = _year_from_question(text, max(r["year"] for r in records))
        year_records = [r for r in records if r["year"] == year]
        if not year_records:
            return f"No EPA records are loaded for model year {year}. Download the EPA data and try again."
        sales_records = sales.get("records", [])
        if not sales_records:
            return "Download sales data as well as EPA mileage so I can compare ratings for the sales models."

        requested_nameplate = _requested_nameplate(text, sales_records)
        sales_index = _sales_model_index(sales_records)
        electric = any(term in lowered for term in ("electric", "mpge")) or bool(
            re.search(r"\bev\b", lowered)
        )
        hydrogen = "hydrogen" in lowered or "mi/kg" in lowered
        if requested_nameplate:
            candidate_year_records = [
                record for record in year_records
                if requested_nameplate in _matched_sales_names(record, sales_index)
            ]
        else:
            candidate_year_records = year_records
        matched = [
            (record, _matched_sales_names(record, sales_index))
            for record in candidate_year_records
        ]
        matched = [(record, names) for record, names in matched if names]
        if not matched:
            return (
                f"No unambiguous exact model matches were found between {year} EPA records "
                "and the downloaded sales nameplates. Unmatched vehicles are not guessed."
            )
        if hydrogen:
            eligible = [(record, names) for record, names in matched if _is_hydrogen(record)]
            metric = "combined_miles_per_kg"
            unit = "combined miles/kg"
        elif electric:
            eligible = [(record, names) for record, names in matched if _is_electric(record)]
            metric = "combined_mpg_or_mpge"
            unit = "MPGe"
        else:
            eligible = [
                (record, names) for record, names in matched
                if not _is_electric(record) and not _is_hydrogen(record)
            ]
            metric = "combined_mpg_or_mpge"
            unit = "combined MPG"
        if requested_nameplate:
            eligible = [
                (record, names) for record, names in eligible
                if requested_nameplate in names
            ]
        if not eligible:
            if requested_nameplate:
                return f"No matched EPA {unit} ratings were found for {requested_nameplate} in model year {year}."
            kind = "hydrogen miles/kg" if hydrogen else ("electric MPGe" if electric else "non-electric MPG")
            return f"No matched {kind} ratings are available for model year {year}."
        eligible = [(record, names) for record, names in eligible if record.get(metric) is not None]
        if not eligible:
            return f"No matched {unit} ratings are available for model year {year}."
        if requested_nameplate:
            configurations = sorted(
                eligible,
                key=lambda item: (
                    item[0].get("model", ""),
                    item[0].get("city_mpg") or 0,
                    item[0].get("highway_mpg") or 0,
                ),
            )
            details = "; ".join(
                f'{record["model"]}: '
                f'{record.get("city_mpg") or "?"} city / '
                f'{record.get("highway_mpg") or "?"} highway / '
                f'{record[metric]:g} {unit}'
                for record, _ in configurations[:5]
            )
            more = (
                f" Showing 5 of {len(configurations)} configurations."
                if len(configurations) > 5 else ""
            )
            sales_detail = ""
            if _has_sales_intent(text):
                sales_year_records = [
                    record for record in sales_records
                    if record["year"] == year
                    and f'{record["make"]} {record["model"]}' == requested_nameplate
                ]
                if sales_year_records:
                    total = sum(record["units"] for record in sales_year_records)
                    months = sorted({record["month"] for record in sales_year_records})
                    if months:
                        period = (
                            f"{calendar.month_name[months[0]]} through "
                            f"{calendar.month_name[months[-1]]}"
                        )
                    else:
                        period = "the available period"
                    sales_source = next(
                        (record.get("source_url") for record in sales_year_records
                         if record.get("source_url")),
                        "GoodCarBadCar",
                    )
                    sales_detail = (
                        f" The sales source lists {total:,} {requested_nameplate} sales "
                        f"for {year} across {period}; coverage may vary by model and "
                        "estimate status is not specified per row. "
                        f"Sales source: {sales_source}."
                    )
                else:
                    sales_detail = (
                        f" No {year} sales records for {requested_nameplate} are loaded."
                    )
            return (
                f"EPA {year} fuel economy for {requested_nameplate}: {details}.{more} "
                "EPA ratings are by vehicle configuration, not sales-weighted. "
                f'Source: {configurations[0][0]["source"]} '
                f'({configurations[0][0]["source_url"]}).{sales_detail}'
            )
        best, names = max(eligible, key=lambda item: item[0][metric])
        unit_note = "" if hydrogen or electric else "EV MPGe and hydrogen miles/kg are reported separately. "
        return (
            f"Among the downloaded sales nameplates with an unambiguous EPA match, the highest "
            f"{year} EPA {unit} is "
            f'{best["make"]} {best["model"]} ({best[metric]:g} {unit}; '
            f'{best["fuel_type"] or "fuel type not listed"}). This is a configuration rating, '
            f'for {", ".join(sorted(names))}; not a sales-weighted model average. '
            f'{len({name for _, matched_names in matched for name in matched_names})} sales '
            f"nameplates had an exact or supported alias match. {unit_note}"
            f'Source: {best["source"]} ({best["source_url"]}).'
        )

    if any(term in lowered for term in ("sold", "sales", "sell", "selling")):
        year = _year_from_question(text, 2025)
        totals = _sales_totals(sales, year)
        if not totals:
            return f"No sales data is loaded for {year}. Use “Download {year} sales” first."
        source_url = next(
            (r["source_url"] for r in sales.get("records", [])
             if r["year"] == year and r.get("source_url")),
            sales.get("source_url", "GoodCarBadCar"),
        )
        nameplate = _matching_sales_nameplate(text, totals)
        months = sorted({
            r["month"] for r in sales.get("records", []) if r["year"] == year
        })
        if nameplate:
            count = totals[nameplate]
            period = (
                f"{calendar.month_name[months[0]]} through {calendar.month_name[months[-1]]}"
                if months else "the available period"
            )
            return (
                f"The source lists {count:,} {nameplate} sales for {year} across {period}. "
                "Coverage can vary by model; the source does not label estimate status per row. "
                f"Source: {source_url}."
            )
        if any(term in lowered for term in ("most", "best-selling", "top", "highest")):
            name, count = max(totals.items(), key=lambda item: item[1])
            return (
                f"The highest listed model total for {year} is {name} with {count:,} units "
                "in the available sales data. Coverage can vary by model; source estimate "
                f"status is not specified per row. Source: {source_url}."
            )
        return (
            "Which model do you mean? Try “How many Honda CR-Vs sold in 2025?” "
            "or “Which model sold the most in 2025?”"
        )

    return (
        "I can answer questions about available 2025/2026 model sales and EPA mileage, "
        "such as “How many Ford F-Series sold in 2025?” or “Which car has the best mileage?”"
    )
