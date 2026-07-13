import os

import numpy as np
import pandas as pd


def numeric_series(df, column, default=0):
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(default)


def normalize(series, invert=False, default=0.5):
    values = pd.to_numeric(series, errors="coerce")
    if values.notna().any():
        values = values.fillna(values.median())
    else:
        values = values.fillna(default)

    minimum = values.min()
    maximum = values.max()
    if maximum == minimum:
        normalized = pd.Series(default, index=values.index, dtype="float64")
    else:
        normalized = (values - minimum) / (maximum - minimum)

    if invert:
        normalized = 1 - normalized
    return normalized.clip(0, 1)


def bool_series(df, column):
    if column not in df.columns:
        return pd.Series(False, index=df.index)
    return df[column].astype(str).str.lower().str.strip().isin(["true", "yes", "y", "1"])


def availability_score(status):
    status_text = str(status).lower()
    if "pre-book" in status_text or "upcoming" in status_text:
        return 0.65
    if "discontinued" in status_text:
        return 0.2
    return 1.0


def engineer_features():
    clean_path = 'data/ev_cars_cleaned.csv'
    if not os.path.exists(clean_path):
        raise FileNotFoundError(f"{clean_path} not found. Run data_cleaning.py first.")

    df = pd.read_csv(clean_path)

    price = numeric_series(df, 'price_on_road_lakh')
    real_range = numeric_series(df, 'real_world_range_km')
    claimed_range = numeric_series(df, 'claimed_range_km')
    battery = numeric_series(df, 'battery_capacity_kwh')
    dc_minutes = numeric_series(df, 'charging_time_dc_minutes', 120)
    ac_hours = numeric_series(df, 'charging_time_ac_hours', 10)
    motor_power = numeric_series(df, 'motor_power_kw')
    acceleration = numeric_series(df, 'acceleration_0_100_sec', 15)
    seats = numeric_series(df, 'seating_capacity', 5)
    boot_space = numeric_series(df, 'boot_space_litres')
    safety = numeric_series(df, 'safety_rating', 3).clip(0, 5)
    fast_charging = bool_series(df, 'fast_charging_available')

    df['price_score'] = normalize(price, invert=True)
    df['range_score'] = normalize(real_range.fillna(claimed_range * 0.78))
    df['battery_score'] = normalize(battery)

    charging_score = normalize(dc_minutes, invert=True)
    charging_score = charging_score + np.where(fast_charging, 0.18, -0.12)
    df['charging_score'] = pd.Series(charging_score, index=df.index).clip(0, 1)

    df['safety_score'] = (safety / 5.0).clip(0, 1)

    norm_power = normalize(motor_power)
    norm_accel = normalize(acceleration, invert=True)
    df['performance_score'] = (norm_power * 0.55) + (norm_accel * 0.45)

    norm_seats = normalize(seats)
    norm_boot = normalize(boot_space)
    df['family_score'] = (norm_seats * 0.35) + (norm_boot * 0.25) + (df['safety_score'] * 0.40)

    body_city_scores = {
        'compact': 1.0,
        'hatchback': 0.92,
        'compact suv': 0.78,
        'suv': 0.62,
        'muv/mpv': 0.58,
        'muv': 0.58,
        'mpv': 0.58,
        'sedan': 0.64,
        'crossover': 0.58,
        'coupe': 0.50,
        'convertible': 0.45,
    }
    df['city_size_score'] = (
        df.get('body_type', pd.Series('SUV', index=df.index))
        .astype(str)
        .str.lower()
        .map(body_city_scores)
        .fillna(0.55)
    )
    ac_score = normalize(ac_hours, invert=True)
    df['city_score'] = (df['city_size_score'] * 0.45) + (df['range_score'] * 0.35) + (ac_score * 0.20)

    df['highway_score'] = (df['range_score'] * 0.52) + (df['charging_score'] * 0.28) + (df['performance_score'] * 0.20)

    average_traits = (
        df['range_score'] +
        df['family_score'] +
        df['safety_score'] +
        df['charging_score'] +
        df['performance_score']
    ) / 5.0
    df['value_for_money_score'] = (average_traits * 0.55) + (df['price_score'] * 0.45)

    latest_sales = numeric_series(df, 'sales_latest_month')
    previous_sales = numeric_series(df, 'sales_previous_month')
    three_month_sales = numeric_series(df, 'sales_3_months_ago')
    average_sales = pd.concat([latest_sales, previous_sales, three_month_sales], axis=1).replace(0, np.nan).mean(axis=1).fillna(0)
    df['sales_volume_score'] = normalize(np.log1p(average_sales))

    raw_momentum = np.where(previous_sales > 0, latest_sales / previous_sales, np.where(latest_sales > 0, 1.12, 1.0))
    df['sales_momentum_score'] = pd.Series((np.clip(raw_momentum, 0.55, 1.55) - 0.55) / 1.0, index=df.index).clip(0, 1)

    rating_count = numeric_series(df, 'rating_count')
    df['rating_count_score'] = normalize(np.log1p(rating_count))

    df['availability_score'] = df.get('status', pd.Series('', index=df.index)).apply(availability_score)
    variants = numeric_series(df, 'variants_count', 1)
    df['variant_depth_score'] = normalize(variants)

    df['popularity_score'] = (
        df['sales_volume_score'] * 0.52 +
        df['sales_momentum_score'] * 0.12 +
        df['rating_count_score'] * 0.08 +
        df['variant_depth_score'] * 0.08 +
        df['value_for_money_score'] * 0.12 +
        df['availability_score'] * 0.08
    ).clip(0, 1)

    output_path = 'data/ev_cars_features.csv'
    df.to_csv(output_path, index=False)
    print(f"Feature-engineered data successfully saved to {output_path}")


if __name__ == '__main__':
    engineer_features()
