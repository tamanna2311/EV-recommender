# EV Finder

Frontend : https://ev-recommender-frontend-lo29.onrender.com
can install app on phone using frontend link 

Backend : https://ev-recommender-64pm.onrender.com/docs

EV Finder recommends electric cars for the Indian market using a hybrid of market popularity, user behavior, and explicit preference scoring.

## What the App Does

- Shows pre-search recommendations as soon as the user lands on Explore.
- Uses cold-start popularity when there is no user history yet.
- Learns from local browser behavior such as searches and opened car listings.
- Lets users fine-tune recommendations by budget, range, family size, use case, body type, brand, charging, and priority.
- Shows image-led car cards with price, range, battery, sales signal, source link, reasons, and drawbacks.
- Includes EV news, accelerometer-based EV ride detection, and sharing views.

## Recommendation Logic

The recommender now has two paths:

1. **Before-search recommendations**
   - No behavior: ranks cars using sales volume, value-for-money, range, safety, charging, and availability.
   - With behavior: blends brand, body type, price, range, and viewed-car affinity with market popularity.

2. **Preference search**
   - Applies budget and seating filters with controlled relaxation.
   - Scores budget, real-world range, charging, family comfort, performance, safety, value, body type, brand, and use case.
   - Adds a small popularity signal and optional behavior signal without letting it overpower explicit preferences.

The first behavior store is intentionally local-only through `localStorage`, so the feature works without login. If user accounts are added later, those events can move to a database with the same event shape.

## Dataset

The app uses `data/ev_cars_features.csv`, generated from:

- `data/market_ev_cars_reference.csv`: broad Indian EV model reference data with images and source URLs.
- `data/monthly_sales_modelwise_2026_05.csv`: model-wise sales signal used for popularity.
- `scripts/import_market_dataset.py`: imports the market CSV into the canonical schema.
- `src/data_cleaning.py` and `src/feature_engineering.py`: clean fields and build recommender scores.

The current checked-in market dataset contains 62 EV models.

## Data Refresh

To refresh from a local CSV:

```bash
python scripts/import_market_dataset.py \
  --source-csv path/to/indian_ev_cars.csv \
  --sales-csv data/monthly_sales_modelwise_2026_05.csv \
  --output-dir data
python src/data_cleaning.py
python src/feature_engineering.py
python -m pytest tests/test_recommender.py -v
```

For ongoing updates, `.github/workflows/update-ev-data.yml` runs weekly and can pull a maintained CSV from the `EV_MARKET_CSV_URL` repository secret. When the generated data changes, it opens a pull request after tests pass.

## How to Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the FastAPI backend:

```bash
uvicorn backend.main:app --reload
```

Run the mobile/PWA frontend from another terminal:

```bash
cd mobile
python -m http.server 8080
```

Open `http://127.0.0.1:8080`.

Run tests:

```bash
python -m pytest tests/test_recommender.py -v
```
