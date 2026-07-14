from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote
import xml.etree.ElementTree as ET
import pandas as pd
import requests
import sys
import os

# Add src to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.recommender import get_default_recommendations, get_recommendations, load_feature_data
from src.explanation_generator import generate_explanation, generate_market_explanation
from src.ev_detector import predict_accelerometer_csv

app = FastAPI(title="EV Car Recommendation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_private_network_cors_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response

NEWS_QUERIES = [
    "electric vehicles India",
    "EV charging India",
    "electric car India",
    "EV battery India",
]
NEWS_CACHE = {
    "expires_at": datetime.min.replace(tzinfo=timezone.utc),
    "payload": None,
    "last_error": "",
}

class BehaviorEvent(BaseModel):
    type: str = "view"
    car_id: str | None = None
    brand: str | None = None
    body_type: str | None = None
    budget_lakh: float | None = None
    minimum_range_km: float | None = None
    preferred_body_type: str | None = None
    brand_preference: str | None = None
    weight: float = 1.0
    created_at: str | None = None


class BehaviorRequest(BaseModel):
    events: list[BehaviorEvent] = Field(default_factory=list)
    limit: int = 6


class UserPreferences(BaseModel):
    budget_lakh: float
    minimum_range_km: float
    daily_travel_km: float
    city: str
    state: str
    use_case: str
    preferred_body_type: str
    family_size: int
    home_charging_available: bool
    fast_charging_needed: bool
    brand_preference: str
    priority: str
    behavior_events: list[BehaviorEvent] = Field(default_factory=list)

def load_data():
    return load_feature_data()


def dataframe_records(df):
    return df.astype(object).where(pd.notnull(df), None).to_dict(orient="records")

def parse_news_date(value):
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)

def clean_google_news_title(title, source):
    suffix = f" - {source}"
    if source and title.endswith(suffix):
        return title[:-len(suffix)].strip()
    return title.strip()

def fetch_news_feed(query):
    feed_url = (
        "https://news.google.com/rss/search?"
        f"q={quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    )
    response = requests.get(
        feed_url,
        headers={
            "User-Agent": "Mozilla/5.0 EV-Recommender/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
        timeout=8,
    )
    response.raise_for_status()
    root = ET.fromstring(response.content)

    articles = []
    for item in root.findall("./channel/item"):
        title = item.findtext("title", default="").strip()
        link = item.findtext("link", default="").strip()
        source = item.findtext("source", default="").strip()
        published_raw = item.findtext("pubDate", default="")
        published_at = parse_news_date(published_raw)

        if not title or not link:
            continue

        articles.append({
            "title": clean_google_news_title(title, source),
            "source": source or "Google News",
            "url": link,
            "published_at": published_at.isoformat(),
            "topic": query,
        })

    return articles

def get_ev_news(limit=12):
    now = datetime.now(timezone.utc)
    if NEWS_CACHE["payload"] and NEWS_CACHE["expires_at"] > now and NEWS_CACHE["payload"].get("articles"):
        return NEWS_CACHE["payload"]

    articles_by_title = {}
    errors = []
    for query in NEWS_QUERIES:
        try:
            for article in fetch_news_feed(query):
                key = article["title"].lower()
                if key not in articles_by_title:
                    articles_by_title[key] = article
        except Exception as exc:
            errors.append(f"{query}: {type(exc).__name__}")
            continue

    articles = sorted(
        articles_by_title.values(),
        key=lambda item: item["published_at"],
        reverse=True,
    )[:limit]

    if not articles:
        NEWS_CACHE["last_error"] = "; ".join(errors)
        if NEWS_CACHE["payload"] and NEWS_CACHE["payload"].get("articles"):
            stale_payload = dict(NEWS_CACHE["payload"])
            stale_payload["stale"] = True
            stale_payload["updated_at"] = now.isoformat()
            return stale_payload
        return {
            "articles": [],
            "updated_at": now.isoformat(),
            "error": NEWS_CACHE["last_error"],
        }

    payload = {
        "articles": articles,
        "updated_at": now.isoformat(),
        "stale": False,
    }
    NEWS_CACHE["payload"] = payload
    NEWS_CACHE["expires_at"] = now + timedelta(minutes=15)
    NEWS_CACHE["last_error"] = ""
    return payload

@app.get("/")
def read_root():
    return {"status": "success", "message": "EV Car Recommendation API is running"}

@app.get("/cars")
def get_all_cars():
    df = load_data()
    return {"cars": dataframe_records(df)}

@app.get("/cars/{car_id}")
def get_car(car_id: str):
    df = load_data()
    car = df[df['car_id'] == car_id]
    if len(car) == 0:
        raise HTTPException(status_code=404, detail="Car not found")
    return dataframe_records(car)[0]

@app.get("/news")
def get_news():
    news = get_ev_news()
    if not news["articles"]:
        raise HTTPException(status_code=503, detail="EV news is temporarily unavailable")
    return news

@app.post("/detect")
async def detect_ev_from_accelerometer(request: Request):
    csv_bytes = await request.body()
    if not csv_bytes:
        raise HTTPException(status_code=400, detail="Accelerometer CSV is empty")

    try:
        return predict_accelerometer_csv(csv_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def car_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).lower().strip() in {"true", "yes", "1", "y"}


def car_number(value, default=0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def car_text(value):
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value) if value is not None else ""


def recommendation_payload(car, rank, prefs=None, personalized=False):
    match_percentage = int(car_number(car.get('final_score')) * 100)
    if prefs:
        reason, drawbacks = generate_explanation(car, prefs, match_percentage)
    else:
        reason, drawbacks = generate_market_explanation(car, personalized=personalized)

    return {
        "rank": rank,
        "car_id": car_text(car.get('car_id')),
        "car_name": car_text(car.get('car_name')),
        "brand": car_text(car.get('brand')),
        "model": car_text(car.get('model')),
        "body_type": car_text(car.get('body_type')),
        "price_lakh": car_number(car.get('price_on_road_lakh')),
        "price_text": car_text(car.get('price_text')) or f"Rs {car_number(car.get('price_on_road_lakh')):.2f} Lakh",
        "claimed_range_km": car_number(car.get('claimed_range_km')),
        "real_world_range_km": car_number(car.get('real_world_range_km')),
        "range_text": car_text(car.get('range_text')) or f"{car_number(car.get('claimed_range_km')):.0f} km",
        "battery_capacity_kwh": car_number(car.get('battery_capacity_kwh')),
        "battery_text": car_text(car.get('battery_text')) or f"{car_number(car.get('battery_capacity_kwh')):.1f} kWh",
        "charging_time_ac_hours": car_number(car.get('charging_time_ac_hours')),
        "charging_time_dc_minutes": car_number(car.get('charging_time_dc_minutes')),
        "charging_text": car_text(car.get('charging_text')),
        "fast_charging_available": car_bool(car.get('fast_charging_available')),
        "safety_rating": car_number(car.get('safety_rating'), 0),
        "seating_capacity": int(car_number(car.get('seating_capacity'), 0)),
        "boot_space_litres": car_number(car.get('boot_space_litres')),
        "ground_clearance_mm": car_number(car.get('ground_clearance_mm')),
        "motor_power_kw": car_number(car.get('motor_power_kw')),
        "torque_nm": car_number(car.get('torque_nm')),
        "top_speed_kmph": car_number(car.get('top_speed_kmph')),
        "acceleration_0_100_sec": car_number(car.get('acceleration_0_100_sec')),
        "warranty_years": car_number(car.get('warranty_years')),
        "battery_warranty_years": car_number(car.get('battery_warranty_years')),
        "battery_warranty_km": car_number(car.get('battery_warranty_km')),
        "sales_latest_month": int(car_number(car.get('sales_latest_month'), 0)),
        "popularity_score": round(car_number(car.get('popularity_score')), 3),
        "match_percentage": match_percentage,
        "reason": reason,
        "drawbacks": drawbacks,
        "pros": car_text(car.get('pros')),
        "cons": car_text(car.get('cons')),
        "useful_features": car_text(car.get('useful_features')),
        "data_source": car_text(car.get('data_source')),
        "last_updated": car_text(car.get('last_updated')),
        "image_url": car_text(car.get('image_url')),
        "source_url": car_text(car.get('source_url')),
        "status": car_text(car.get('status')),
    }


@app.post("/recommend/personalized")
def recommend_from_behavior(payload: BehaviorRequest):
    limit = min(max(payload.limit, 1), 12)
    top_cars = get_default_recommendations(payload.events, limit=limit)
    personalized = bool(payload.events)
    return {
        "mode": "personalized" if personalized else "popular",
        "recommendations": [
            recommendation_payload(car, rank, personalized=personalized)
            for rank, (_, car) in enumerate(top_cars.iterrows(), start=1)
        ],
    }


@app.post("/recommend")
def recommend_cars(prefs: UserPreferences):
    top_cars = get_recommendations(prefs, behavior_events=prefs.behavior_events)
    
    if len(top_cars) == 0:
        return {"recommendations": []}
        
    recommendations = [
        recommendation_payload(car, rank, prefs=prefs, personalized=bool(prefs.behavior_events))
        for rank, (_, car) in enumerate(top_cars.iterrows(), start=1)
    ]
        
    return {"recommendations": recommendations}
