from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

from src.recommender import get_recommendations
from src.explanation_generator import generate_explanation
from src.ev_detector import predict_accelerometer_csv

app = FastAPI(title="EV Car Recommendation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NEWS_QUERIES = [
    "electric vehicles India",
    "EV charging India",
    "electric car India",
    "EV battery India",
]
NEWS_CACHE = {
    "expires_at": datetime.min.replace(tzinfo=timezone.utc),
    "payload": None,
}

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

def load_data():
    try:
        return pd.read_csv('data/ev_cars_features.csv')
    except:
        return pd.read_csv('../data/ev_cars_features.csv')

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
    response = requests.get(feed_url, headers={"User-Agent": "EV-Recommender/1.0"}, timeout=8)
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
    if NEWS_CACHE["payload"] and NEWS_CACHE["expires_at"] > now:
        return NEWS_CACHE["payload"]

    articles_by_title = {}
    for query in NEWS_QUERIES:
        try:
            for article in fetch_news_feed(query):
                key = article["title"].lower()
                if key not in articles_by_title:
                    articles_by_title[key] = article
        except Exception:
            continue

    articles = sorted(
        articles_by_title.values(),
        key=lambda item: item["published_at"],
        reverse=True,
    )[:limit]

    payload = {
        "articles": articles,
        "updated_at": now.isoformat(),
    }
    NEWS_CACHE["payload"] = payload
    NEWS_CACHE["expires_at"] = now + timedelta(minutes=15)
    return payload

@app.get("/")
def read_root():
    return {"status": "success", "message": "EV Car Recommendation API is running"}

@app.get("/cars")
def get_all_cars():
    df = load_data()
    return {"cars": df.to_dict(orient="records")}

@app.get("/cars/{car_id}")
def get_car(car_id: str):
    df = load_data()
    car = df[df['car_id'] == car_id]
    if len(car) == 0:
        raise HTTPException(status_code=404, detail="Car not found")
    return car.to_dict(orient="records")[0]

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

@app.post("/recommend")
def recommend_cars(prefs: UserPreferences):
    top_cars = get_recommendations(prefs)
    
    if len(top_cars) == 0:
        return {"recommendations": []}
        
    recommendations = []
    rank = 1
    for _, car in top_cars.iterrows():
        match_percentage = int(car['final_score'] * 100)
        reason, drawbacks = generate_explanation(car, prefs, match_percentage)
        
        rec = {
            "rank": rank,
            "car_name": car['car_name'],
            "brand": car['brand'],
            "price_lakh": car['price_on_road_lakh'],
            "claimed_range_km": car['claimed_range_km'],
            "battery_capacity_kwh": car['battery_capacity_kwh'],
            "match_percentage": match_percentage,
            "reason": reason,
            "drawbacks": drawbacks
        }
        recommendations.append(rec)
        rank += 1
        
    return {"recommendations": recommendations}
