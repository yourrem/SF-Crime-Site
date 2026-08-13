# SF Crime Site

A Python ETL pipeline that pulls SF crime data from the SF Open Data Portal (Socrata API) and displays it on a simple Flask web app.

## Project status
Core ETL pipeline is complete. Postgres is set up with 1M+ historical records loaded. Next focus areas: website improvements, PostGIS, or dbt.

## How to run

```bash
# Run the full pipeline (incremental upsert for both feeds)
python3 scripts/run_pipeline.py

# Run each pipeline individually
python3 scripts/run_pipeline.py incidents   # last 2 days, upserts into Postgres
python3 scripts/run_pipeline.py calls       # last 2 hours, upserts into Postgres

# One-time historical backfill (already done — do not re-run)
python3 scripts/backfill_incidents.py

# Start the web app
python3 app.py
# Then open http://127.0.0.1:5000
```

## Project structure
```
etl/
  extract.py    — Socrata API calls (requests + SoQL filtering, pagination, 30s timeout)
  transform.py  — clean_incidents(): types, dedup, flags missing location rows
  load.py       — load() replaces table, upsert() inserts new rows only (Postgres via SQLAlchemy)
scripts/
  run_pipeline.py         — incremental daily/real-time pipeline runner
  backfill_incidents.py   — one-time historical load, year by year (already run)
notebooks/
  01_explore_incidents.ipynb  — Step 2 data exploration
templates/
  index.html    — barebones Flask table view (last 100 incidents)
app.py          — Flask web server
```

## Data sources
Both from data.sfgov.org (Socrata API — requires app token in .env):
- **Daily incident reports** — dataset ID `wg3w-h783`, incremental upsert on `row_id`
- **Real-time calls for service** — dataset ID `gnap-fj3t`, incremental upsert on `cad_number`, updates every 10 min

## Database
- **Postgres** (migrated from SQLite)
- Database name: `sfcrime`
- Tables: `incidents` (1,054,314 rows as of Aug 2026), `calls`
- Connection via `POSTGRES_URL` in `.env`
- View data with TablePlus (localhost, port 5432, db: sfcrime, no password)

## Automation
Cron jobs (run `crontab -l` to verify):
```
*/10 * * * *  → run_pipeline.py calls      (real-time feed)
0 6  * * *    → run_pipeline.py incidents   (daily feed)
```
Logs: `logs/calls.log` and `logs/incidents.log`

## Environment
Requires a `.env` file in the project root:
```
SOCRATA_APP_TOKEN=your_token_here
POSTGRES_URL=postgresql://localhost/sfcrime
```

## Key decisions
- **Upsert not replace** — `run_pipeline.py` uses `upsert()` so daily runs never wipe existing data
- **Backfill runs year by year** — Socrata times out at high offsets; chunking by year avoids this
- **days=2 for incidents** — dataset has a 1-2 day reporting lag so `days=1` returns nothing
- **dict-valued columns dropped at load time** — Socrata returns GeoJSON columns pandas/Postgres can't handle directly
- **filed_online column dropped** — ~1100 NAs, no analytical value
- **Rows with missing location data kept** — flagged with `has_location=False`, not dropped
- **SQLite removed** — fully migrated to Postgres; PostGIS is the planned next step for geo queries

## Completed steps
1. ✅ Pull daily incidents with `requests`, print raw JSON
2. ✅ Load into pandas, explore columns/types/nulls (notebook)
3. ✅ SoQL filtering (last N days) with pagination
4. ✅ `clean_incidents(df)` — types, dedup, flag missing location
5. ✅ Store in database via `df.to_sql()`
6. ✅ Chain into `run_pipeline.py`
7. ✅ Real-time calls feed with upsert logic
8. ✅ Cron automation
9. ✅ Basic Flask website
10. ✅ Migrated to Postgres
11. ✅ Full historical backfill (1M+ rows)

## Next steps (pick one)
- **PostGIS** — add geospatial extension to Postgres for location-based queries
- **Website improvements** — pagination, filtering by category/district, map view
- **dbt** — SQL transformations on top of Postgres (good DE resume skill)
- **Airflow** — revisit orchestration once pipeline stabilizes (installed but parked for now)
- **Logging** — swap print() for Python logging module
