# SF Crime Site — Project Context

An end-to-end data engineering + ML pipeline pulling SF crime data from SF Open Data (Socrata API), loading into Postgres, transforming with dbt, forecasting with scikit-learn, and displaying on a Flask web app. Orchestrated with Apache Airflow.

## How to run

```bash
# Start Airflow (runs both DAGs on schedule automatically)
airflow standalone
# UI at http://localhost:8080

# Run the pipeline manually
python3 scripts/run_pipeline.py incidents   # auto-detects how many days are missing
python3 scripts/run_pipeline.py calls       # last 2 hours
python3 scripts/run_pipeline.py all         # both

# Run dbt transformations manually
cd sfcrime_dbt && dbt run

# Retrain the forecast model manually
python3 scripts/train_forecast.py

# Start the web app
python3 app.py
# http://127.0.0.1:5000           — overview: KPI cards + intersection map
# http://127.0.0.1:5000/district  — by neighborhood: date range, accordion, charts
# http://127.0.0.1:5000/trends    — trend charts (daily, monthly, quarterly)
# http://127.0.0.1:5000/category  — by category: date range, expandable time charts
# http://127.0.0.1:5000/forecast  — Ridge regression forecast + confidence band
# http://127.0.0.1:5000/recent    — pipeline log: last 10 incidents + calls

# Full data reset (wipe + reload from Socrata)
# 1. Truncate tables, flush Redis — see "Data reset" section below
# 2. python3 scripts/backfill_incidents.py   (~8-10 hrs, run overnight)
# 3. cd sfcrime_dbt && dbt run --full-refresh
# 4. python3 scripts/train_forecast.py
```

## Project structure
```
etl/
  extract.py          — Socrata API calls, SoQL filtering, pagination, 30s timeout
  transform.py        — clean_incidents(): types, dedup, flag missing location
  load.py             — upsert() inserts new rows only (Postgres via SQLAlchemy)
scripts/
  run_pipeline.py     — incremental pipeline (smart date detection + logging)
  backfill_incidents.py — historical load, year-by-year (safe to re-run after TRUNCATE)
  train_forecast.py   — Ridge regression model: reads daily_trends, writes crime_forecast
dags/
  sfcrime_pipeline.py — Airflow DAGs (symlinked from ~/airflow/dags/)
sfcrime_dbt/
  models/staging/
    stg_incidents.sql         — TABLE materialization: dedup + quality flags + indexes
    sources.yml / schema.yml
  models/marts/
    daily_trends.sql          — daily count + 7-day rolling avg
    incidents_by_category.sql — counts by category and date
    incidents_by_district.sql — counts by district (has known bug — see Gotchas)
ml/
  forecast_model.pkl  — serialized Ridge model (gitignored, rebuilt by train_forecast.py)
templates/
  index.html          — overview: KPI cards + emoji-marker intersection map + legend
  district.html       — by neighborhood: date range, accordion, expandable charts
  trends.html         — daily bar/line, month-by-month (year picker), all-time quarterly
  category.html       — by category: date range, expandable time distribution charts
  forecast.html       — actual vs predicted chart, shaded confidence band, KPI strip
  recent.html         — pipeline log: last 10 incidents + calls
app.py                — Flask web server + Redis caching
logs/
  pipeline.log        — rotating log from run_pipeline.py (5MB, 3 backups)
Dockerfile            — python:3.12-slim, gunicorn on port 8080
Procfile              — web: gunicorn app:app
runtime.txt           — python-3.12 (Fly.io)
```

## Flask routes
Pages:
- `GET /` — overview (KPI cards, intersection map)
- `GET /district` — by neighborhood
- `GET /trends` — trend charts
- `GET /category` — by category
- `GET /forecast` — crime forecast
- `GET /recent` — pipeline log

API (all cached via Flask-Caching + Redis, 5-min TTL):
- `GET /api/latest-date` — MAX(incident_date) from DB; used by all pages to anchor date pickers (1hr TTL)
- `GET /api/trends` — daily incidents + 7-day rolling avg (last 90 days)
- `GET /api/map-incidents?days=` — top 700 intersections with per-category crime breakdown
- `GET /api/neighborhoods?start&end&limit` — top neighborhoods (default limit=15)
- `GET /api/neighborhood/categories?neighborhood&start&end` — top 8 categories for one neighborhood
- `GET /api/neighborhood/time?neighborhood&granularity&start&end` — time breakdown (hour/dow/month/year)
- `GET /api/districts/trends?days` — daily per-district counts for top 5
- `GET /api/monthly?year` — month-by-month counts for given year
- `GET /api/quarterly` — all-time quarterly counts
- `GET /api/categories?start&end` — top categories with incident counts
- `GET /api/category/time?category&start&end` — hourly time distribution for a category
- `GET /api/forecast` — actuals + 30-day predictions + confidence band

## Airflow automation
Two DAGs in `dags/sfcrime_pipeline.py` (symlinked to `~/airflow/dags/`):
- **sfcrime_incidents_daily** — 6am daily: `fetch_incidents → run_dbt → retrain_forecast`
- **sfcrime_calls_realtime** — every 10 min: `fetch_calls`

Both DAGs: 2 retries, 5-min retry delay, paused=False.
Start with `airflow standalone`. Smart date detection catches up automatically after missed runs.

## Database
- **Postgres**, database: `sfcrime`
- **Raw tables:** `public.incidents` (~1M+ rows, 2018–present), `public.calls`
- **Analytics schema:**
  - `analytics.stg_incidents` — TABLE (not view); deduped, quality-flagged, indexed
  - `analytics.daily_trends` — daily counts + 7-day rolling avg
  - `analytics.incidents_by_category` — counts by category
  - `analytics.incidents_by_district` — counts by district (has known bug — see Gotchas)
  - `analytics.crime_forecast` — 30-day forward predictions (written by train_forecast.py)
  - `analytics.forecast_meta` — model metrics: MAE, RMSE, train rows, trained_at
- **Indexes on stg_incidents:** `idx_stg_incidents_date`, `idx_stg_incidents_neighborhood_date`
- View data: TablePlus (localhost, port 5432, db: sfcrime, no password)
- dbt profile: `~/.dbt/profiles.yml`

## Machine learning
`scripts/train_forecast.py`:
- Reads `analytics.daily_trends`; features: lag_1, lag_7, lag_30, day_of_week, month, year, is_weekend
- Train/test split: 90-day holdout. Ridge(alpha=1.0). Serialized to `ml/forecast_model.pkl`
- Recursive 30-day forward forecast; predictions + ±1 RMSE confidence band written to `analytics.crime_forecast`
- Wired into Airflow DAG: runs nightly after `run_dbt`
- As of last full reset (2026-09): MAE ~27.7/day, RMSE ~36.2 on 3,039-day training set

## Caching
Flask-Caching with Redis (5-min default TTL). Falls back to SimpleCache if `REDIS_URL` is not set.
```python
if os.getenv("REDIS_URL"):
    cache = Cache(app, config={"CACHE_TYPE": "RedisCache", "CACHE_REDIS_URL": os.getenv("REDIS_URL"), ...})
else:
    cache = Cache(app, config={"CACHE_TYPE": "SimpleCache", ...})
```
Start Redis locally: `redis-server --daemonize yes --logfile /tmp/redis.log`
Clear cache: `redis-cli FLUSHDB`

## Data reset procedure
Use when doing a full sanity-check reset:
```bash
# 1. Pause Airflow
airflow dags pause sfcrime_incidents_daily
airflow dags pause sfcrime_calls_realtime

# 2. Clear Redis
redis-cli FLUSHDB

# 3. Truncate tables (in psql sfcrime)
TRUNCATE public.incidents;
TRUNCATE public.calls;
TRUNCATE analytics.crime_forecast;
TRUNCATE analytics.forecast_meta;

# 4. Delete stale model
rm -f ml/forecast_model.pkl

# 5. Re-run backfill (8-10 hrs — run overnight)
python3 scripts/backfill_incidents.py

# 6. Rebuild dbt analytics tables
cd sfcrime_dbt && dbt run --full-refresh

# 7. Retrain forecast
cd .. && python3 scripts/train_forecast.py

# 8. Unpause Airflow
airflow dags unpause sfcrime_incidents_daily
airflow dags unpause sfcrime_calls_realtime
```
Note: `backfill_incidents.py` is safe to re-run as long as you TRUNCATE first.

## Data sources
Both from data.sfgov.org (Socrata API — `SOCRATA_APP_TOKEN` in `.env`):
- **Incident reports** — dataset `wg3w-h783`, upsert on `row_id`
- **Calls for service** — dataset `gnap-fj3t`, upsert on `cad_number`

## Environment
`.env` file in project root (gitignored):
```
SOCRATA_APP_TOKEN=your_token_here
POSTGRES_URL=postgresql://localhost/sfcrime
```
For Fly.io: app reads `POSTGRES_URL` then falls back to `DATABASE_URL` (auto-set by Fly when Postgres is attached). `REDIS_URL` must be set manually via `fly secrets set`.

## Chart color palette
10-color muted palette used consistently across all Chart.js charts:
```js
const PALETTE = [
    '#5B8DB8','#5A9990','#6A9E78','#8E9E5A','#C4952E',
    '#C4714E','#B07A8A','#8E7AAB','#7A82B5','#9B7B4A',
];
function colorFor(name) {
    let h = 0;
    for (const c of name) h = (h * 31 + c.charCodeAt(0)) & 0xffff;
    return PALETTE[h % PALETTE.length];
}
```
Hash is stable — a name always maps to the same color regardless of sort order.

## Gotchas
- **`incidents_by_district` bug** — mart has inverted `AND NOT is_valid_location` filter, returns 0 rows. Do NOT fix. All district/neighborhood API endpoints query `analytics.stg_incidents` directly instead.
- **SQLAlchemy text() colon parsing** — `':00'` is parsed as bind param `00`. Use `chr(58)` to produce a literal colon in SQL strings.
- **JS let/const TDZ** — don't call functions that reference `let`/`const` variables before their declaration line in the same script block.
- **Fly.io env** — `POSTGRES_URL` is not auto-set; app falls back to `DATABASE_URL`. `REDIS_URL` must be set manually.
- **Date range anchoring** — all date-picker pages fetch `/api/latest-date` on init and anchor range buttons to `MAX(incident_date)`, not `new Date()`. This prevents 24h/7d tabs from returning no data when the pipeline hasn't run today.
- **`/api/map-incidents` CTE** — groups incidents by intersection with full per-category breakdown. The `top_ix` CTE limits to 700 intersections before joining back to category rows to avoid returning 10k+ rows.

## Key decisions
- **ELT not ETL** — raw data lands in Postgres untouched; dbt handles all transformations
- **Upsert, never replace** — `upsert()` uses staging table + `WHERE NOT IN`; 1M rows never wiped
- **Smart date detection** — `run_incidents()` queries `MAX(incident_date)` to auto-calculate missing days
- **Backfill year-by-year** — Socrata times out at high offsets; chunking by year avoids this
- **Flag, don't delete** — bad data flagged in dbt staging (`is_unfounded`, `is_non_criminal`, `is_valid_location`); mart models filter
- **stg_incidents as TABLE** — materialized as table (not view) with composite indexes; eliminates full table scans on API queries
- **Redis with SimpleCache fallback** — app starts cleanly without Redis; Fly.io sets REDIS_URL in secrets
- **Recursive forecast** — each predicted value feeds next day's lag inputs; avoids data leakage in forward projection
