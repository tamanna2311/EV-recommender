#!/usr/bin/env python3
"""Import a broad Indian EV market CSV into the recommender data schema.

The app scores a canonical feature file. This script lets us refresh that file
from a richer market source instead of hand-editing Python dictionaries every
time a model is launched.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen


BASE_FIELDS = [
    "car_id",
    "car_name",
    "brand",
    "model",
    "variant",
    "price_ex_showroom_lakh",
    "price_on_road_lakh",
    "min_price_lakh",
    "max_price_lakh",
    "battery_capacity_kwh",
    "claimed_range_km",
    "real_world_range_km",
    "charging_time_ac_hours",
    "charging_time_dc_minutes",
    "fast_charging_available",
    "motor_power_kw",
    "torque_nm",
    "top_speed_kmph",
    "acceleration_0_100_sec",
    "body_type",
    "segment",
    "seating_capacity",
    "boot_space_litres",
    "ground_clearance_mm",
    "safety_rating",
    "airbags",
    "transmission",
    "drive_type",
    "warranty_years",
    "battery_warranty_years",
    "battery_warranty_km",
    "home_charging_supported",
    "pros",
    "cons",
    "source_url",
    "last_updated",
]

EXTENDED_FIELDS = [
    "status",
    "price_text",
    "range_text",
    "battery_text",
    "charging_text",
    "useful_features",
    "variants_count",
    "image_url",
    "image_source_url",
    "data_source",
    "data_collected_date",
    "notes",
    "sales_latest_month",
    "sales_previous_month",
    "sales_3_months_ago",
    "sales_data_month",
    "sales_source",
]

FIELDNAMES = BASE_FIELDS + EXTENDED_FIELDS


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return re.sub(r"_+", "_", slug)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def number(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip().replace(",", "")
    if not text:
        return default
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else default


def first_number(value: object, default: float = 0.0) -> float:
    return number(value, default)


def parse_safety_rating(value: str) -> float:
    rating = first_number(value, 0)
    if rating:
        return min(5.0, max(0.0, rating))
    return 3.0


def parse_ac_hours(charging_text: str, battery_kwh: float) -> float:
    text = charging_text.lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*hrs?(?:\s*(\d{1,2}))?", text)
    if match:
        hours = float(match.group(1))
        minutes = float(match.group(2) or 0)
        return round(hours + minutes / 60, 2)
    return round(max(2.0, battery_kwh / 7.2), 2)


def estimate_dc_minutes(fast_charging: bool, battery_kwh: float, min_price_lakh: float) -> float:
    if not fast_charging:
        return 120.0
    if min_price_lakh >= 50:
        return 28.0
    if battery_kwh >= 70:
        return 36.0
    if battery_kwh >= 45:
        return 45.0
    return 52.0


def estimate_segment(body_type: str, min_price_lakh: float) -> str:
    body = body_type.strip() or "SUV"
    if min_price_lakh >= 80:
        return f"Luxury {body}"
    if min_price_lakh >= 35:
        return f"Premium {body}"
    if body.lower() in {"compact", "hatchback"}:
        return "City Hatchback"
    if body.lower() in {"muv/mpv", "muv", "mpv"}:
        return "Family MPV"
    if min_price_lakh <= 18 and "suv" in body.lower():
        return "Compact SUV"
    return body


def estimate_motor_power(body_type: str, min_price_lakh: float, battery_kwh: float) -> float:
    body_defaults = {
        "compact": 35,
        "hatchback": 55,
        "suv": 105,
        "compact suv": 95,
        "muv/mpv": 105,
        "sedan": 140,
        "coupe": 220,
        "convertible": 220,
    }
    base = body_defaults.get(body_type.lower(), 100)
    if min_price_lakh >= 200:
        base += 240
    elif min_price_lakh >= 100:
        base += 140
    elif min_price_lakh >= 50:
        base += 70
    elif min_price_lakh >= 25:
        base += 25
    if battery_kwh >= 90:
        base += 35
    elif battery_kwh >= 60:
        base += 15
    return float(base)


def estimate_boot_space(body_type: str, seats: int) -> float:
    body = body_type.lower()
    if seats >= 7:
        return 300.0
    if "muv" in body or "mpv" in body:
        return 450.0
    if "hatch" in body or body == "compact":
        return 250.0
    if "sedan" in body:
        return 420.0
    if "coupe" in body or "convertible" in body:
        return 300.0
    return 380.0


def estimate_ground_clearance(body_type: str) -> float:
    body = body_type.lower()
    if "suv" in body:
        return 190.0
    if "muv" in body or "mpv" in body:
        return 180.0
    if "hatch" in body or body == "compact":
        return 170.0
    return 160.0


def load_sales(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    return {row["car_id"]: row for row in read_csv(path)}


def market_row_to_canonical(row: dict[str, str], sales_rows: dict[str, dict[str, str]]) -> dict[str, object]:
    brand = row.get("Brand", "").strip()
    model = row.get("Model", "").strip()
    car_id = slugify(f"{brand} {model}")
    min_price = number(row.get("Price_Lakh_Min"))
    max_price = number(row.get("Price_Lakh_Max"), min_price)
    range_min = number(row.get("Range_km_Min"))
    range_max = number(row.get("Range_km_Max"), number(row.get("Range_km")))
    battery_min = number(row.get("Battery_capacity_kWh_Min"))
    battery_max = number(row.get("Battery_capacity_kWh_Max"), number(row.get("Battery_capacity_kWh")))
    fast_charging = row.get("Fast_Charging", "").strip().lower() == "yes"
    seats = int(number(row.get("Seats"), 5))
    body_type = row.get("Body_Type", "").strip() or "SUV"
    safety_rating = parse_safety_rating(row.get("Safety_Rating", ""))
    battery_kwh = battery_max or battery_min
    claimed_range = range_max or range_min
    range_text = row.get("Range_Text", "")
    if "real" in range_text.lower():
        real_range = claimed_range
    else:
        real_range = max(range_min, round(claimed_range * 0.78, 0))
    ac_hours = parse_ac_hours(row.get("Charging_time", ""), battery_kwh)
    dc_minutes = estimate_dc_minutes(fast_charging, battery_kwh, min_price)
    motor_power = estimate_motor_power(body_type, min_price, battery_kwh)
    acceleration = max(3.3, min(15.5, 16 - (motor_power / 24)))
    sales = sales_rows.get(car_id, {})

    canonical = {
        "car_id": car_id,
        "car_name": f"{brand} {model}".strip(),
        "brand": brand,
        "model": model,
        "variant": "Model range",
        "price_ex_showroom_lakh": round(min_price, 2),
        "price_on_road_lakh": round(min_price, 2),
        "min_price_lakh": round(min_price, 2),
        "max_price_lakh": round(max_price, 2),
        "battery_capacity_kwh": round(battery_kwh, 2),
        "claimed_range_km": round(claimed_range, 0),
        "real_world_range_km": round(real_range, 0),
        "charging_time_ac_hours": ac_hours,
        "charging_time_dc_minutes": dc_minutes,
        "fast_charging_available": "Yes" if fast_charging else "No",
        "motor_power_kw": round(motor_power, 1),
        "torque_nm": round(motor_power * 2.45, 0),
        "top_speed_kmph": round(min(250, max(95, 95 + motor_power * 0.35)), 0),
        "acceleration_0_100_sec": round(acceleration, 1),
        "body_type": body_type,
        "segment": estimate_segment(body_type, min_price),
        "seating_capacity": seats,
        "boot_space_litres": estimate_boot_space(body_type, seats),
        "ground_clearance_mm": estimate_ground_clearance(body_type),
        "safety_rating": safety_rating,
        "airbags": 6 if safety_rating >= 5 or min_price >= 15 else 2,
        "transmission": "Automatic",
        "drive_type": "FWD" if min_price < 30 else "RWD/AWD",
        "warranty_years": 3,
        "battery_warranty_years": 8,
        "battery_warranty_km": 160000,
        "home_charging_supported": "Yes",
        "pros": row.get("Useful_Features", "").strip(),
        "cons": row.get("Notes", "").strip(),
        "source_url": row.get("Source_URL", "").strip(),
        "last_updated": date.today().isoformat(),
        "status": row.get("Status", "").strip(),
        "price_text": row.get("Price_Text", "").strip(),
        "range_text": range_text.strip(),
        "battery_text": row.get("Battery_Text", "").strip(),
        "charging_text": row.get("Charging_time", "").strip(),
        "useful_features": row.get("Useful_Features", "").strip(),
        "variants_count": int(number(row.get("Variants_Count"), 1)),
        "image_url": row.get("Image_URL", "").strip(),
        "image_source_url": row.get("Image_Source_URL", "").strip(),
        "data_source": row.get("Data_Source", "").strip(),
        "data_collected_date": row.get("Data_Collected_Date", "").strip(),
        "notes": row.get("Notes", "").strip(),
        "sales_latest_month": sales.get("sales_latest_month", ""),
        "sales_previous_month": sales.get("sales_previous_month", ""),
        "sales_3_months_ago": sales.get("sales_3_months_ago", ""),
        "sales_data_month": sales.get("sales_data_month", ""),
        "sales_source": sales.get("sales_source", ""),
    }
    return canonical


def resolve_source_csv(args: argparse.Namespace) -> Path:
    if args.source_url:
        request = Request(args.source_url, headers={"User-Agent": "EV-Recommender-Data-Refresh/1.0"})
        with urlopen(request, timeout=30) as response:
            data = response.read()
        temp_path = Path(tempfile.gettempdir()) / "indian_ev_market_source.csv"
        temp_path.write_bytes(data)
        return temp_path
    return Path(args.source_csv)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-csv", default="data/market_ev_cars_reference.csv")
    parser.add_argument("--source-url", default="", help="Optional CSV URL for scheduled refreshes.")
    parser.add_argument("--sales-csv", default="data/monthly_sales_modelwise_2026_05.csv")
    parser.add_argument("--output-dir", default="data")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    source_csv = resolve_source_csv(args)
    sales_path = Path(args.sales_csv) if args.sales_csv else None
    sales_rows = load_sales(sales_path)
    market_rows = read_csv(source_csv)
    canonical_rows = [market_row_to_canonical(row, sales_rows) for row in market_rows]

    reference_path = output_dir / "market_ev_cars_reference.csv"
    if source_csv.resolve() != reference_path.resolve():
        reference_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_csv, reference_path)

    write_csv(output_dir / "raw_ev_data.csv", canonical_rows, FIELDNAMES)
    print(f"Imported {len(canonical_rows)} cars to {output_dir / 'raw_ev_data.csv'}")
    print("Next: python src/data_cleaning.py && python src/feature_engineering.py")


if __name__ == "__main__":
    main()
