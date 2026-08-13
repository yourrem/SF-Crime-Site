import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
from etl.extract import fetch_incidents
from etl.transform import clean_incidents
from etl.load import load

# Fetch and load one year at a time to avoid Socrata timeout at high offsets
YEARS = range(2018, 2027)

for year in YEARS:
    start = f"{year}-01-01T00:00:00"
    end = f"{year}-12-31T23:59:59"
    print(f"\n--- Fetching {year} ---")

    raw = fetch_incidents(start_date=start, end_date=end)
    if not raw:
        print(f"  No records for {year}, skipping")
        continue

    df = pd.DataFrame(raw)
    df_clean = clean_incidents(df)
    print(f"  Cleaned shape: {df_clean.shape}")

    # append so each year adds to the table instead of replacing it
    from sqlalchemy import text
    from etl.load import ENGINE, _prepare
    df_ready = _prepare(df_clean)
    with ENGINE.begin() as conn:
        df_ready.to_sql("incidents", conn, if_exists="append", index=False)
        count = conn.execute(text("SELECT COUNT(*) FROM incidents")).scalar()
        print(f"  Table now has {count} rows")

print("\nBackfill complete.")
