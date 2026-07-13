from pathlib import Path

import numpy as np
import pandas as pd


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "ev_cars_features.csv"


def load_feature_data():
    return pd.read_csv(DATA_PATH)


def value_from(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def number(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def boolean(value):
    if isinstance(value, bool):
        return value
    return str(value).lower().strip() in {"true", "yes", "y", "1"}


def get_base_weights(priority):
    weights = {
        'budget_score': 0.25,
        'range_score': 0.20,
        'charging_score': 0.15,
        'family_score': 0.15,
        'performance_score': 0.10,
        'safety_score': 0.15,
    }

    if priority == 'lowest_price':
        weights.update({'budget_score': 0.48, 'value_for_money_score': 0.14, 'range_score': 0.14, 'family_score': 0.06, 'performance_score': 0.04, 'safety_score': 0.14, 'charging_score': 0.0})
    elif priority == 'maximum_range':
        weights.update({'range_score': 0.48, 'budget_score': 0.15, 'charging_score': 0.16, 'family_score': 0.10, 'performance_score': 0.05, 'safety_score': 0.06})
    elif priority == 'fast_charging':
        weights.update({'charging_score': 0.40, 'range_score': 0.24, 'budget_score': 0.14, 'family_score': 0.10, 'performance_score': 0.06, 'safety_score': 0.06})
    elif priority == 'family_comfort':
        weights.update({'family_score': 0.38, 'safety_score': 0.24, 'budget_score': 0.15, 'range_score': 0.12, 'charging_score': 0.06, 'performance_score': 0.05})
    elif priority == 'performance':
        weights.update({'performance_score': 0.38, 'range_score': 0.21, 'budget_score': 0.14, 'family_score': 0.09, 'charging_score': 0.12, 'safety_score': 0.06})
    elif priority == 'safety':
        weights.update({'safety_score': 0.40, 'family_score': 0.20, 'budget_score': 0.15, 'range_score': 0.14, 'charging_score': 0.06, 'performance_score': 0.05})

    return weights


def calculate_budget_score(car_price, user_budget):
    if user_budget <= 0:
        return 0.0
    if car_price <= user_budget:
        return 1.0 - (car_price / user_budget) * 0.2
    overage = car_price - user_budget
    return max(0.0, 1.0 - (overage / (user_budget * 0.5)))


def calculate_match_score(car, prefs, weights):
    score = 0.0
    budget = number(value_from(prefs, 'budget_lakh'), 15)
    minimum_range = number(value_from(prefs, 'minimum_range_km'), 250)
    use_case = value_from(prefs, 'use_case', 'daily_city_commute')
    preferred_body_type = value_from(prefs, 'preferred_body_type', 'Any')
    brand_preference = value_from(prefs, 'brand_preference', 'Any')

    car_price = number(car.get('price_on_road_lakh'))
    car_real_range = number(car.get('real_world_range_km'))
    budget_score = calculate_budget_score(car_price, budget)
    score += budget_score * weights.get('budget_score', 0)

    if minimum_range <= 0 or car_real_range >= minimum_range:
        range_match = 1.0
    else:
        range_match = max(0.0, car_real_range / minimum_range)

    combined_range_score = (range_match * 0.7) + (number(car.get('range_score')) * 0.3)
    score += combined_range_score * weights.get('range_score', 0)

    for column in ['charging_score', 'family_score', 'performance_score', 'safety_score', 'value_for_money_score']:
        score += number(car.get(column)) * weights.get(column, 0)

    if use_case == 'daily_city_commute':
        score += number(car.get('city_score')) * 0.10
    elif use_case == 'highway_travel':
        score += number(car.get('highway_score')) * 0.10
    elif use_case == 'budget_friendly':
        score += number(car.get('value_for_money_score')) * 0.10
    elif use_case == 'premium':
        score += (number(car.get('performance_score')) * 0.05) + (number(car.get('range_score')) * 0.05)

    if preferred_body_type != 'Any' and str(car.get('body_type', '')).lower() == str(preferred_body_type).lower():
        score += 0.05

    if brand_preference != 'Any' and str(car.get('brand', '')).lower() == str(brand_preference).lower():
        score += 0.05

    return score


def normalize_counts(counts):
    total = sum(counts.values())
    if total <= 0:
        return {}
    return {key: value / total for key, value in counts.items()}


def event_to_dict(event):
    if isinstance(event, dict):
        return event
    if hasattr(event, "model_dump"):
        return event.model_dump()
    if hasattr(event, "dict"):
        return event.dict()
    return {}


def build_behavior_profile(events):
    profile = {
        "brands": {},
        "body_types": {},
        "car_ids": {},
        "budgets": [],
        "ranges": [],
        "has_signal": False,
    }
    event_dicts = [event_to_dict(event) for event in (events or [])][-60:]
    if not event_dicts:
        return profile

    for index, event in enumerate(event_dicts):
        recency_weight = 0.96 ** (len(event_dicts) - index - 1)
        event_type = event.get("type", "view")
        base_weight = number(event.get("weight"), 1.0)
        if event_type == "search":
            base_weight *= 1.15
        elif event_type in {"view_car", "open_source"}:
            base_weight *= 1.35
        weight = base_weight * recency_weight

        car_id = event.get("car_id")
        if car_id:
            profile["car_ids"][car_id] = profile["car_ids"].get(car_id, 0) + weight
        brand = event.get("brand") or event.get("brand_preference")
        if brand and brand != "Any":
            profile["brands"][brand] = profile["brands"].get(brand, 0) + weight
        body_type = event.get("body_type") or event.get("preferred_body_type")
        if body_type and body_type != "Any":
            profile["body_types"][body_type] = profile["body_types"].get(body_type, 0) + weight
        budget = event.get("budget_lakh")
        if budget:
            profile["budgets"].append(number(budget) * weight)
        minimum_range = event.get("minimum_range_km")
        if minimum_range:
            profile["ranges"].append(number(minimum_range) * weight)

    profile["brands"] = normalize_counts(profile["brands"])
    profile["body_types"] = normalize_counts(profile["body_types"])
    profile["car_ids"] = normalize_counts(profile["car_ids"])
    profile["average_budget"] = np.mean(profile["budgets"]) if profile["budgets"] else None
    profile["average_range"] = np.mean(profile["ranges"]) if profile["ranges"] else None
    profile["has_signal"] = bool(profile["brands"] or profile["body_types"] or profile["car_ids"] or profile["budgets"] or profile["ranges"])
    return profile


def calculate_behavior_score(car, profile):
    if not profile.get("has_signal"):
        return 0.0

    score = 0.0
    car_id = str(car.get('car_id', ''))
    brand = str(car.get('brand', ''))
    body_type = str(car.get('body_type', ''))
    score += profile["car_ids"].get(car_id, 0) * 0.20
    score += profile["brands"].get(brand, 0) * 0.24
    score += profile["body_types"].get(body_type, 0) * 0.20

    average_budget = profile.get("average_budget")
    if average_budget:
        price = number(car.get('price_on_road_lakh'))
        distance = abs(price - average_budget) / max(average_budget, 1)
        score += max(0.0, 1.0 - distance) * 0.18

    average_range = profile.get("average_range")
    if average_range:
        car_range = number(car.get('real_world_range_km'))
        range_fit = 1.0 if car_range >= average_range else car_range / max(average_range, 1)
        score += max(0.0, min(1.0, range_fit)) * 0.10

    score += number(car.get('popularity_score')) * 0.08
    return min(1.0, max(0.0, score))


def apply_preference_filters(df, prefs):
    budget = number(value_from(prefs, 'budget_lakh'), 15)
    family_size = number(value_from(prefs, 'family_size'), 4)

    filtered_df = df.copy()
    strict_budget = budget * 1.10
    filtered_df = filtered_df[filtered_df['price_on_road_lakh'] <= strict_budget]
    filtered_df = filtered_df[filtered_df['seating_capacity'] >= family_size]

    if len(filtered_df) < 5:
        filtered_df = df.copy()
        filtered_df = filtered_df[filtered_df['price_on_road_lakh'] <= budget * 1.5]

    return filtered_df


def get_recommendations(prefs, behavior_events=None, limit=5):
    df = load_feature_data()
    filtered_df = apply_preference_filters(df, prefs)
    weights = get_base_weights(value_from(prefs, 'priority', 'balanced'))
    profile = build_behavior_profile(behavior_events or value_from(prefs, 'behavior_events', []))
    fast_charging_needed = boolean(value_from(prefs, 'fast_charging_needed', False))
    budget = number(value_from(prefs, 'budget_lakh'), 15)
    family_size = number(value_from(prefs, 'family_size'), 4)

    scores = []
    for _, car in filtered_df.iterrows():
        score = calculate_match_score(car, prefs, weights)

        if number(car['price_on_road_lakh']) > budget:
            score -= 0.10
        if number(car['seating_capacity']) < family_size:
            score -= 0.20
        if fast_charging_needed and not boolean(car['fast_charging_available']):
            score -= 0.15

        score += number(car.get('popularity_score')) * 0.05
        if profile.get("has_signal"):
            score = (score * 0.86) + (calculate_behavior_score(car, profile) * 0.14)

        scores.append(min(1.0, max(0.0, score)))

    filtered_df = filtered_df.copy()
    filtered_df['final_score'] = scores
    return filtered_df.sort_values(by='final_score', ascending=False).head(limit)


def market_relevance_frame(df):
    price = pd.to_numeric(df['price_on_road_lakh'], errors='coerce').fillna(0)
    sales = pd.to_numeric(df.get('sales_latest_month', 0), errors='coerce').fillna(0)
    relevant = df[(price <= 80) | (sales > 0)].copy()
    if len(relevant) < 6:
        return df.copy()
    return relevant


def get_default_recommendations(behavior_events=None, limit=6):
    df = market_relevance_frame(load_feature_data())
    profile = build_behavior_profile(behavior_events)
    scores = []

    for _, car in df.iterrows():
        if profile.get("has_signal"):
            score = (
                calculate_behavior_score(car, profile) * 0.50 +
                number(car.get('popularity_score')) * 0.26 +
                number(car.get('value_for_money_score')) * 0.14 +
                number(car.get('range_score')) * 0.06 +
                number(car.get('availability_score')) * 0.04
            )
        else:
            score = (
                number(car.get('popularity_score')) * 0.48 +
                number(car.get('value_for_money_score')) * 0.20 +
                number(car.get('range_score')) * 0.14 +
                number(car.get('safety_score')) * 0.10 +
                number(car.get('charging_score')) * 0.08
            )
        scores.append(min(1.0, max(0.0, score)))

    df = df.copy()
    df['final_score'] = scores
    return df.sort_values(by='final_score', ascending=False).head(limit)
