def generate_explanation(car, prefs, match_percentage):
    reasons = []
    drawbacks = []
    
    # 1. Budget
    if car['price_on_road_lakh'] <= prefs.budget_lakh:
        reasons.append("fits comfortably within your budget")
    else:
        overage = car['price_on_road_lakh'] - prefs.budget_lakh
        drawbacks.append(f"is slightly over your budget by {overage:.2f} Lakh")
        
    # 2. Range
    if car['real_world_range_km'] >= prefs.minimum_range_km:
        reasons.append("meets your minimum range requirement")
    else:
        drawbacks.append("has a lower real-world range than you requested")
        
    # 3. Use Case Specifics
    if prefs.use_case == 'daily_city_commute':
        if car['city_score'] > 0.6:
            reasons.append("is highly suitable for city driving")
    elif prefs.use_case == 'highway_travel':
        if car['highway_score'] > 0.6:
            reasons.append("performs well on highway trips")
        else:
            drawbacks.append("may not be ideal for frequent long highway trips")
            
    # 4. Family & Seats
    if car['seating_capacity'] >= prefs.family_size:
        reasons.append(f"can easily accommodate your family of {prefs.family_size}")
    else:
        drawbacks.append(f"has only {car['seating_capacity']} seats, which is less than you need")
        
    # 5. Charging
    if prefs.fast_charging_needed:
        if car['fast_charging_available']:
            reasons.append("supports fast charging as requested")
        else:
            drawbacks.append("does not support fast charging")
            
    # 6. Safety
    if car['safety_rating'] >= 4:
        reasons.append(f"has a strong {int(car['safety_rating'])}-star safety rating")
    elif car['safety_rating'] <= 2:
        drawbacks.append(f"has a low {int(car['safety_rating'])}-star safety rating")
        
    # Combine reasons
    if reasons:
        reason_text = f"{car['car_name']} is recommended because it " + ", ".join(reasons[:-1])
        if len(reasons) > 1:
            reason_text += f", and {reasons[-1]}."
        else:
            reason_text += f"{reasons[0]}."
    else:
        reason_text = f"{car['car_name']} is an alternative option."
        
    # Combine drawbacks
    if drawbacks:
        drawback_text = "However, it " + ", ".join(drawbacks[:-1])
        if len(drawbacks) > 1:
            drawback_text += f", and {drawbacks[-1]}."
        else:
            drawback_text += f"{drawbacks[0]}."
    else:
        drawback_text = "It perfectly matches most of your core requirements."
        
    return reason_text, drawback_text


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def generate_market_explanation(car, personalized=False):
    reasons = []
    sales = _safe_float(car.get('sales_latest_month'))
    real_range = _safe_float(car.get('real_world_range_km'))
    price = _safe_float(car.get('price_on_road_lakh'))

    if sales > 0:
        reasons.append(f"{int(sales):,} recent monthly sales")
    if _safe_float(car.get('value_for_money_score')) >= 0.65:
        reasons.append("strong value for the price")
    if real_range >= 350:
        reasons.append(f"about {int(real_range)} km estimated real-world range")
    if _safe_float(car.get('safety_rating'), 3) >= 5:
        reasons.append("a 5-star safety rating")
    if car.get('fast_charging_available') in [True, 'True', 'true', 'Yes', 'yes']:
        reasons.append("fast-charging support")

    if personalized:
        prefix = "Recommended from your recent browsing"
    else:
        prefix = "Popular starting point"

    if not reasons:
        return f"{prefix} based on current market availability.", ""

    first_reasons = ", ".join(reasons[:3])
    price_text = f" Starts around Rs {price:.2f} lakh." if price else ""
    return f"{prefix}: {first_reasons}.{price_text}", ""
