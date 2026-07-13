# How to Run EV Finder

## 1. Install Dependencies

Use Python 3.11 or 3.12.

```bash
pip install -r requirements.txt
```

## 2. Refresh Data

The checked-in dataset is already generated. To rebuild it from a market CSV:

```bash
python scripts/import_market_dataset.py \
  --source-csv data/market_ev_cars_reference.csv \
  --sales-csv data/monthly_sales_modelwise_2026_05.csv \
  --output-dir data
python src/data_cleaning.py
python src/feature_engineering.py
```

To refresh from an online CSV source:

```bash
python scripts/import_market_dataset.py \
  --source-url "$EV_MARKET_CSV_URL" \
  --sales-csv data/monthly_sales_modelwise_2026_05.csv \
  --output-dir data
python src/data_cleaning.py
python src/feature_engineering.py
```

## 3. Run Backend

```bash
uvicorn backend.main:app --reload
```

API docs are available at `http://127.0.0.1:8000/docs`.

## 4. Run Mobile/PWA Frontend

```bash
cd mobile
python -m http.server 8080
```

Open `http://127.0.0.1:8080`.

The frontend automatically uses `http://127.0.0.1:8000` when run locally. In production it uses the deployed API URL in `mobile/app.js`.

## 5. Optional Streamlit Frontend

```bash
API_URL=http://127.0.0.1:8000 streamlit run frontend/app.py
```

## 6. Run Tests

```bash
python -m pytest tests/test_recommender.py -v
```
