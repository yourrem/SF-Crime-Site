# SF Crime Site

A Python ETL pipeline that pulls SF crime data from the SF Open Data Portal (Socrata API) and displays it on a simple Flask web app.

## Project status
Working through a step-by-step plan. Currently on Step 7 — adding the real-time calls-for-service dataset with upsert logic.

## How to run

```bash
# Run the full pipeline (extract → clean → load to SQLite)
python3 scripts/run_pipeline.py

# Start the web app
python3 app.py
# Then open http://127.0.0.1:5000
```

## Project structure
```
etl/
  extract.py    — pulls data from Socrata API (requests + SoQL filtering)
  transform.py  — cleans types, drops junk columns, flags missing location rows
  load.py       — writes to SQLite; load() replaces, upsert() for incremental feeds
scripts/
  run_pipeline.py  — chains extract → transform → load end-to-end
notebooks/
  01_explore_incidents.ipynb  — Step 2 exploration of the daily incidents dataset
templates/
  index.html    — barebones Flask table view
data/
  sfcrime.db    — SQLite database (gitignored)
app.py          — Flask web server
```

## Data sources
Both from data.sfgov.org (Socrata API, requires app token):
- **Daily incident reports** — dataset ID `wg3w-h783`, used in the current pipeline
- **Real-time calls for service** — dataset ID TBD, updates every 10 minutes (Step 7)

## Key decisions
- **SQLite over Postgres** — intentional for the learning phase; will migrate to Postgres + PostGIS later for geospatial queries
- **One dataset at a time** — daily feed first, real-time feed second (Step 7)
- **Rows with missing location data are kept** — flagged with `has_location=False` for later investigation, not dropped
- **`filed_online` column dropped** — ~1100 NAs, no analytical value
- **`point` column dropped at load time** — dict type unsupported by SQLite; lat/long columns already capture the coordinates

## Environment
Requires a `.env` file in the project root:
```
SOCRATA_APP_TOKEN=your_token_here
```

## Step-by-step build plan
1. ✅ Pull daily incidents with `requests`, print raw JSON
2. ✅ Load into pandas, explore columns/types/nulls
3. ✅ SoQL filtering (last 7 days) with pagination
4. ✅ `clean(df)` function — types, dedup, flag missing location
5. ✅ Store in SQLite via `df.to_sql()`
6. ✅ Chain into `run_pipeline.py`
7. ⬜ Add real-time calls-for-service feed with upsert logic
8. ⬜ Automate with cron
