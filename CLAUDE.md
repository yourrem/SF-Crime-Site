# SF Crime Site — Project Context

A Python ELT pipeline that pulls SF crime data from the SF Open Data Portal (Socrata API), loads it into Postgres, transforms it with dbt, and displays it on a Flask web app. Orchestrated with Apache Airflow.

## How to run

```bash
# Start Airflow (runs both DAGs on schedule automatically)
airflow standalone
# UI at http://localhost:8080

# Run the pipeline manually (useful for testing)
python3 scripts/run_pipeline.py incidents   # auto-detects how many days are missing
python3 scripts/run_pipeline.py calls       # last 2 hours
python3 scripts/run_pipeline.py all         # both

# Run dbt transformations manually
cd sfcrime_dbt && dbt run

# Start the web app
python3 app.py
# http://127.0.0.1:5000        — overview, KPI cards, heatmap
# http://127.0.0.1:5000/recent — pipeline log (last 10 incidents + calls)

# One-time historical backfill (already done — DO NOT re-run)
python3 scripts/backfill_incidents.py
```

## Project structure
```
etl/
  extract.py    — Socrata API calls, SoQL filtering, pagination, 30s timeout
  transform.py  — clean_incidents(): types, dedup, flag missing location
  load.py       — upsert() inserts new rows only (Postgres via SQLAlchemy)
scripts/
  run_pipeline.py         — incremental pipeline (smart date detection + logging)
  backfill_incidents.py   — one-time historical load, year by year (already run)
dags/
  sfcrime_pipeline.py     — Airflow DAGs (symlinked from ~/airflow/dags/)
sfcrime_dbt/
  models/staging/
    stg_incidents.sql     — deduplicated view with data quality flags
    sources.yml / schema.yml
  models/marts/
    daily_trends.sql        — daily count + 7-day rolling avg
    incidents_by_category.sql
    incidents_by_district.sql
templates/
  index.html    — overview: KPI cards + crime heatmap
  recent.html   — pipeline log: last 10 incidents + calls
app.py          — Flask web server (routes: /, /recent, /api/heatmap)
logs/
  pipeline.log  — rotating log from run_pipeline.py (5MB, 3 backups)
```

## Airflow automation
Two DAGs in `dags/sfcrime_pipeline.py` (symlinked to `~/airflow/dags/`):
- **sfcrime_incidents_daily** — 6am daily: `fetch_incidents → run_dbt` (sequential, dbt depends on load)
- **sfcrime_calls_realtime** — every 10 min: `fetch_calls`

Both DAGs: 2 retries, 5-min retry delay, paused=False.
Start with `airflow standalone`. DAGs will not run while the laptop is asleep — smart date detection catches up automatically on next run.

## Database
- **Postgres**, database: `sfcrime`
- Tables: `public.incidents` (~1M+ rows, 2018–present), `public.calls`
- Analytics schema: `analytics.stg_incidents`, `analytics.daily_trends`, `analytics.incidents_by_category`, `analytics.incidents_by_district`
- View data: TablePlus (localhost, port 5432, db: sfcrime, no password)
- dbt profile: `~/.dbt/profiles.yml`

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

## Key decisions
- **ELT not ETL** — raw data lands in Postgres untouched; dbt handles all business-logic transformations
- **Upsert, never replace** — `upsert()` uses staging table + `WHERE NOT IN` to skip duplicates; 1M rows are never wiped
- **Smart date detection** — `run_incidents()` queries `MAX(incident_date)` to auto-calculate how many days to fetch; self-healing if runs are missed
- **Backfill year-by-year** — Socrata times out at high offsets; chunking by year avoids this
- **Flag, don't delete** — bad data (`is_unfounded`, `is_non_criminal`, `is_valid_location`) flagged in dbt staging; mart models filter by flags
- **dict columns dropped at load** — Socrata GeoJSON columns can't go into Postgres as-is; dropped in `_prepare()`
- **Python logging module** — rotating file handler in `logs/pipeline.log`; replaces print statements

## Completed steps
1. ✅ Pull daily incidents from Socrata API
2. ✅ Explore with pandas (notebook)
3. ✅ SoQL filtering + pagination
4. ✅ `clean_incidents()` — types, dedup, location flag
5. ✅ Store in database via `df.to_sql()`
6. ✅ Chain into `run_pipeline.py`
7. ✅ Real-time calls feed with upsert
8. ✅ Migrated to Postgres
9. ✅ Full historical backfill (1M+ rows, 2018–2026)
10. ✅ dbt staging model — dedup + data quality flags
11. ✅ dbt mart models — daily_trends, incidents_by_category, incidents_by_district
12. ✅ Flask web app — KPI cards, crime heatmap, pipeline log page
13. ✅ Airflow DAGs — replaced cron, full pipeline orchestration with retries
14. ✅ Smart date detection — auto catch-up if runs are missed
15. ✅ Structured logging — Python logging module with rotation

## Next steps (pick one)
- **Trend chart** — add Chart.js bar/line chart to website using `daily_trends` mart
- **GitHub README** — write a proper README so the repo is presentable for resume links
- **PostGIS** — geospatial extension for neighborhood/district polygon queries
- **More dbt models** — year-over-year comparison, top neighborhoods, hour-of-day breakdown
- **Airflow cloud** — deploy to a VM so pipeline runs 24/7 without laptop
