# SF Crime Tracker

An end-to-end data engineering project that pulls San Francisco crime data from the SF Open Data Portal, loads it into a Postgres data warehouse, transforms it with dbt, and displays it on a live Flask web app — fully automated with Apache Airflow.

## Architecture

```
Socrata API (SF Open Data)
        │
        ▼
  etl/extract.py          ← paginated API calls with SoQL filtering
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
  dbt (sfcrime_dbt/)       ← data quality flags, dedup, mart models
        │
        ▼
  analytics schema         ← daily_trends, incidents_by_category, incidents_by_district
        │
        ▼
  Flask web app            ← KPI cards, crime heatmap, pipeline log
```

**Orchestration:** Apache Airflow — incidents daily at 6am (fetch → dbt), calls every 10 minutes.

## Tech Stack

| Layer | Tool |
|-------|------|
| Extraction | Python, Requests, Socrata SODA API |
| Transformation | pandas, dbt |
| Storage | PostgreSQL |
| Orchestration | Apache Airflow 3.x |
| Web | Flask, Leaflet.js |
| Language | Python 3.14 |

## Features

- **1M+ historical records** loaded via a year-by-year backfill strategy (avoids Socrata API timeouts at high offsets)
- **Incremental upsert** — daily runs never re-process existing data; staging table pattern with `INSERT WHERE NOT IN`
- **Smart catch-up** — pipeline auto-detects `MAX(incident_date)` in Postgres and pulls only what's missing
- **Data quality flags** in dbt staging layer: `is_unfounded`, `is_non_criminal`, `is_valid_location` — bad data is flagged, not deleted
- **Two live data feeds** — historical incidents (daily) and real-time calls for service (every 10 min)
- **Rotating logs** — Python `logging` module with `RotatingFileHandler`
- **Pipeline monitoring page** at `/recent` — shows the last 10 loaded incidents and calls to verify the pipeline is running

## Project Structure

```
etl/
  extract.py              SoQL-filtered paginated API calls
  transform.py            pandas cleaning pipeline
  load.py                 SQLAlchemy upsert logic
scripts/
  run_pipeline.py         CLI entry point (incidents / calls / all)
  backfill_incidents.py   One-time historical load (2018–2026)
dags/
  sfcrime_pipeline.py     Airflow DAGs — incidents daily + calls realtime
sfcrime_dbt/
  models/staging/         stg_incidents: dedup + quality flags
  models/marts/           daily_trends, incidents_by_category, incidents_by_district
templates/
  index.html              Overview: KPIs + heatmap
  recent.html             Pipeline log: last 10 incidents + calls
app.py                    Flask application
```

## Setup

**Prerequisites:** Python 3.x, PostgreSQL, Apache Airflow

```bash
git clone https://github.com/ljsaavedra56ers/SF-Crime-Site.git
cd SF-Crime-Site
pip install -r requirements.txt
```

Create a `.env` file:
```
SOCRATA_APP_TOKEN=your_token_here
POSTGRES_URL=postgresql://localhost/sfcrime
```

Get a free API token at [data.sfgov.org](https://data.sfgov.org).

```bash
# Create the Postgres database
createdb sfcrime

# Run dbt to create analytics schema
cd sfcrime_dbt && dbt run && cd ..

# Start the web app
python3 app.py
```

**Airflow setup:**
```bash
# Symlink the DAG into Airflow's dags folder
ln -s $(pwd)/dags/sfcrime_pipeline.py ~/airflow/dags/sfcrime_pipeline.py

# Start Airflow
airflow standalone
# UI at http://localhost:8080 — unpause both sfcrime DAGs
```

## Data Sources

Both datasets from the [SF Open Data Portal](https://data.sfgov.org) via the Socrata SODA API:

- **SFPD Incident Reports** (`wg3w-h783`) — filed police reports, 2018 to present
- **SFPD Calls for Service** (`gnap-fj3t`) — real-time dispatch calls, updated every ~10 minutes

## Key Design Decisions

**ELT over ETL** — raw data lands in Postgres first; all business-logic cleaning happens in dbt so rules can be changed without re-fetching from the API.

**Flag, don't delete** — rows with `resolution = 'Unfounded'`, category `Non-Criminal`, or coordinates outside SF's bounding box are flagged in the dbt staging layer. Mart models filter on these flags. The raw data is always preserved.

**Year-by-year backfill** — the Socrata API times out at high row offsets. Fetching one year at a time keeps each request under the timeout threshold.

**Upsert with staging table** — incremental loads use a temporary staging table + `INSERT WHERE NOT IN` rather than `ON CONFLICT`, avoiding the need for a `UNIQUE` constraint on the 1M-row table.
