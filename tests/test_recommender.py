import pytest
import sys
import os
import pandas as pd

# Add backend directory to path to import models
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.main import UserPreferences
from src.recommender import get_default_recommendations, get_recommendations

@pytest.fixture(scope="module", autouse=True)
def setup_data():
    # Make sure we are running tests from the project root
    if not os.path.exists('data/ev_cars_features.csv'):
        pytest.fail("Test must be run from the root directory of the project, where data/ev_cars_features.csv exists.")

def test_budget_city_user():
    # Case 1: Budget: 10 lakh, Range: 200 km, Use: city commute, Expected: affordable EVs
    prefs = UserPreferences(
        budget_lakh=10.0,
        minimum_range_km=200,
        daily_travel_km=20,
        city="Mumbai",
        state="MH",
        use_case="daily_city_commute",
        preferred_body_type="Any",
        family_size=4,
        home_charging_available=True,
        fast_charging_needed=False,
        brand_preference="Any",
        priority="lowest_price"
    )
    recs = get_recommendations(prefs)
    
    assert len(recs) > 0
    # Top recommendation should be cheap
    assert recs.iloc[0]['price_on_road_lakh'] <= 12.5 # Allow slight leeway
    # MG Comet or Tiago EV should be up there
    top_brands = recs['brand'].head(3).tolist()
    assert 'MG' in top_brands or 'Tata' in top_brands

def test_family_user():
    # Case 2: Budget: 18 lakh, Range: 300 km, Use: family, Expected: 5-seater EVs with safety and boot space
    prefs = UserPreferences(
        budget_lakh=18.0,
        minimum_range_km=300,
        daily_travel_km=40,
        city="Delhi",
        state="Delhi",
        use_case="family_use",
        preferred_body_type="SUV",
        family_size=5,
        home_charging_available=True,
        fast_charging_needed=True,
        brand_preference="Any",
        priority="family_comfort"
    )
    recs = get_recommendations(prefs)
    
    assert len(recs) > 0
    assert recs.iloc[0]['seating_capacity'] >= 5
    # Should recommend Punch EV, XUV400 or Nexon EV
    assert recs.iloc[0]['body_type'].lower() in ['suv', 'compact suv', 'micro suv']

def test_highway_user():
    # Case 3: Budget: 25 lakh, Range: 400 km, Use: highway, Expected: long-range EVs
    prefs = UserPreferences(
        budget_lakh=25.0,
        minimum_range_km=400,
        daily_travel_km=100,
        city="Pune",
        state="MH",
        use_case="highway_travel",
        preferred_body_type="SUV",
        family_size=5,
        home_charging_available=True,
        fast_charging_needed=True,
        brand_preference="Any",
        priority="maximum_range"
    )
    recs = get_recommendations(prefs)
    
    assert len(recs) > 0
    # Should be something like MG ZS EV or Nexon EV
    assert recs.iloc[0]['price_on_road_lakh'] <= 28.0 # With leeway
    assert recs.iloc[0]['real_world_range_km'] > 320 # closest to 400

def test_premium_user():
    # Case 4: Budget: 50 lakh, Range: 450 km, Use: premium, Expected: premium EVs
    prefs = UserPreferences(
        budget_lakh=50.0,
        minimum_range_km=450,
        daily_travel_km=50,
        city="Bangalore",
        state="KA",
        use_case="premium",
        preferred_body_type="Any",
        family_size=4,
        home_charging_available=True,
        fast_charging_needed=True,
        brand_preference="Any",
        priority="performance"
    )
    recs = get_recommendations(prefs)
    
    assert len(recs) > 0
    # Ioniq 5 or EV6 or BYD Atto 3
    assert recs.iloc[0]['price_on_road_lakh'] > 30.0


def test_cold_start_recommendations_use_market_popularity():
    recs = get_default_recommendations(limit=6)

    assert len(recs) == 6
    assert recs.iloc[0]['popularity_score'] > 0
    assert recs.iloc[0]['price_on_road_lakh'] <= 80


def test_behavior_recommendations_shift_toward_user_affinity():
    events = [
        {
            "type": "search",
            "budget_lakh": 18,
            "minimum_range_km": 300,
            "preferred_body_type": "SUV",
            "brand_preference": "MG",
            "weight": 1.4,
        },
        {
            "type": "open_source",
            "car_id": "mg_windsor_ev",
            "brand": "MG",
            "body_type": "MUV/MPV",
            "budget_lakh": 12.04,
            "minimum_range_km": 350,
            "weight": 1.6,
        },
    ]
    recs = get_default_recommendations(events, limit=3)

    assert len(recs) == 3
    assert "MG" in recs["brand"].head(2).tolist()
