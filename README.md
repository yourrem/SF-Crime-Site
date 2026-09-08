# SF Crime Tracker

An end-to-end data engineering + machine learning system built on 8+ years of SFPD incident data from SF Open Data. Pulls data from a live API, loads it into PostgreSQL, transforms it with dbt, forecasts with Ridge regression, and displays everything on a Flask web app — fully automated with Apache Airflow.

## Architecture

```
Socrata API (SF Open Data)
        │
        ▼
  etl/extract.py          ← paginated SoQL API calls, 30s timeout handling
        │
        ▼
  etl/transform.py        ← type coercion, dedup, location flagging
        │
        ▼
  etl/load.py             ← upsert into Postgres (staging table pattern)
        │
        ▼
  public.incidents         ← 1M+ rows, 2018–present
  public.calls             ← real-time calls for service
        │
        ▼
  dbt (sfcrime_dbt/)       ← quality flags, dedup, mart models + indexes
        │
        ▼
  analytics schema         ← stg_incidents, daily_trends, incidents_by_category,
                              incidents_by_district, crime_forecast, forecast_meta
        │
        ├──► Flask app ──► Redis cache ──► Browser
        │
        └──► train_forecast.py ──► Ridge model ──► crime_forecast table
```

**Orchestration:** Apache Airflow — `fetch_incidents → run_dbt → retrain_forecast` daily at 6am; calls for service every 10 minutes.

**Deployment:** Docker + Fly.io. Redis on managed cloud (Flask-Caching, 5-min TTL).

## Tech Stack

| Layer | Tool |
|---|---|
| Extraction | Python, Requests, Socrata SODA API |
| Transformation | pandas, dbt 1.x |
| Storage | PostgreSQL |
| Orchestration | Apache Airflow 3.x |
| Machine Learning | scikit-learn (Ridge), joblib |
| Caching | Redis, Flask-Caching |
| Web | Flask, Chart.js 4.4, Leaflet.js |
| Deployment | Docker, Fly.io |
| Language | Python 3.12 |

## Web App

| Route | Description |
|---|---|
| `/` | Overview: KPI cards + emoji-marker intersection map with interactive legend |
| `/district` | By Neighborhood: date-range filter, ranked accordion table, expandable charts |
| `/category` | By Category: date-range filter, expandable hourly time-distribution charts |
| `/trends` | Trend charts: daily bar/line, month-by-month (year picker), all-time quarterly |
| `/forecast` | Ridge regression forecast: actual vs predicted line chart + shaded confidence band |
| `/recent` | Pipeline log: last 10 loaded incidents and calls for service |

## Features

**Data pipeline**
- 1M+ historical records loaded via year-by-year backfill (avoids Socrata timeout at high offsets)
- Incremental upsert — daily runs never re-process existing data; staging table pattern
- Smart catch-up — pipeline queries `MAX(incident_date)` and pulls only missing days; self-heals after skipped runs
- Data quality flags in dbt staging: `is_unfounded`, `is_non_criminal`, `is_valid_location` — bad data flagged, not deleted
- `stg_incidents` materialized as a table (not view) with composite indexes on `incident_date` and `(analysis_neighborhood, incident_date)`
- Two live feeds: historical incidents (daily) and real-time calls for service (every 10 min)

**Machine learning**
- Ridge regression model trained on 3,039 days of daily incident history
- Features: lag-1, lag-7, lag-30 incident counts; day of week, month, year, weekend flag
- 90-day holdout test set — MAE 27.7 incidents/day, RMSE 36.2
- Recursive 30-day forward forecast: each predicted value feeds the next day's lag inputs (no data leakage)
- Predictions + ±1 RMSE confidence band written to `analytics.crime_forecast`
- Model retrained nightly by Airflow after dbt completes

**Web app**
- Date-range filtering (24h / 7d / 30d / 90d / YTD / custom) anchored to `MAX(incident_date)` in DB — works correctly even when the pipeline hasn't run today
- Interactive map: emoji markers by crime type at top intersections; clickable legend pills filter visible markers; popups show only selected crime types
- Redis caching on all slow endpoints (~68ms → ~7ms, ~10x speedup); falls back to SimpleCache if Redis unavailable
- Forecast page: Chart.js line chart with solid actuals, dashed predictions, shaded confidence band, and model KPI strip (MAE, RMSE, training rows, last retrained)

## Project Structure

```
etl/
  extract.py              SoQL-filtered paginated API calls
  transform.py            pandas cleaning pipeline
  load.py                 SQLAlchemy upsert logic
scripts/
  run_pipeline.py         CLI entry point (incidents / calls / all)
  backfill_incidents.py   Historical load, year-by-year (safe to re-run after TRUNCATE)
  train_forecast.py       Ridge model training + recursive forecast generation
dags/
  sfcrime_pipeline.py     Airflow DAGs — daily pipeline + realtime calls
sfcrime_dbt/
  models/staging/         stg_incidents: TABLE materialization, dedup, quality flags
  models/marts/           daily_trends, incidents_by_category, incidents_by_district
ml/
  forecast_model.pkl      Serialized Ridge model (gitignored — rebuilt nightly)
templates/
  index.html              Overview: KPIs + intersection map
  district.html           By Neighborhood: date range, accordion, expand charts
  category.html           By Category: date range, time distribution charts
  trends.html             Daily, monthly, quarterly trend charts
  forecast.html           Actual vs predicted + confidence band
  recent.html             Pipeline log
app.py                    Flask application (18 API endpoints, Redis caching)
Dockerfile                python:3.12-slim, gunicorn on port 8080
Procfile                  web: gunicorn app:app
```

## Setup

**Prerequisites:** Python 3.x, PostgreSQL, Apache Airflow, Redis (optional — falls back to in-memory cache)

```bash
git clone https://github.com/yourrem/SF-Crime-Site.git
cd SF-Crime-Site
pip install -r requirements.txt
```

Create a `.env` file:
```
SOCRATA_APP_TOKEN=your_token_here
POSTGRES_URL=postgresql://localhost/sfcrime
# REDIS_URL=redis://localhost:6379/0  (optional)
```

Get a free API token at [data.sfgov.org](https://data.sfgov.org).

```bash
# Create the database and run dbt
createdb sfcrime
cd sfcrime_dbt && dbt run && cd ..

# Load historical data (2018–present, runs overnight)
python3 scripts/backfill_incidents.py

# Train the forecast model
python3 scripts/train_forecast.py

# Start the web app
python3 app.py
```

**Airflow setup:**
```bash
ln -s $(pwd)/dags/sfcrime_pipeline.py ~/airflow/dags/sfcrime_pipeline.py
airflow standalone
# UI at http://localhost:8080 — unpause both sfcrime DAGs
```

## Data Sources

Both datasets from the [SF Open Data Portal](https://data.sfgov.org) via the Socrata SODA API:

- **SFPD Incident Reports** ([`wg3w-h783`](https://data.sfgov.org/Public-Safety/Police-Department-Incident-Reports-2018-to-Present/wg3w-h783)) — filed police reports, 2018 to present
- **SFPD Calls for Service** ([`gnap-fj3t`](https://data.sfgov.org/Public-Safety/Police-Department-Calls-for-Service/gnap-fj3t)) — real-time dispatch calls

## Key Design Decisions

**ELT over ETL** — raw data lands in Postgres first; all business-logic cleaning happens in dbt so rules can be changed without re-fetching from the API.

**Flag, don't delete** — rows flagged `is_unfounded`, `is_non_criminal`, or outside SF's bounding box are preserved in the raw layer; mart models filter on these flags.

**Year-by-year backfill** — the Socrata API times out at high row offsets. Fetching one year at a time keeps each request under the threshold.

**Upsert with staging table** — incremental loads use a temporary staging table + `INSERT WHERE NOT IN` to skip duplicates without requiring a `UNIQUE` constraint on the 1M-row table.

**Recursive forecast** — each predicted value is appended to the history before generating the next day's prediction, so lag features remain valid across the entire 30-day horizon without leaking future data.

**Stable color hashing** — each neighborhood/category name is hashed to a stable index in a 10-color muted palette. The same name always maps to the same color across all charts.
